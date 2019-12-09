#!/usr/bin/env python3
import argparse
import os
import subprocess
import glob
import sys

GIT = os.getenv('GIT', 'git')
GPG = os.getenv('GPG', 'gpg')
GITIAN_PUBKEYS_DIR = os.getenv('GITIAN_PUBKEYS_DIR', 'gitian-pubkeys')

def verify():
    global args, workdir
    if args.import_keys:
        import_gpg_keys()
    if args.refresh_keys:
        refresh_gpg_keys()
    # Shell glob pattern for specific version or all builds:
    ver_pattern = args.version if args.version else 'v0*'
    sig_file_paths = set(glob.glob(ver_pattern + '-*/*/*.assert.sig'))
    assert_files = get_assert_file_list(ver_pattern)
    user_names = get_user_names_from_keys()
    verify_file_path_naming(assert_files, sig_file_paths, user_names)
    verify_gpg_sigs(sig_file_paths)
    verify_checksums(assert_files)
    print('All checks passed.')
    os.chdir(workdir)

def main():
    global args, workdir
    args = get_parsed_args()
    workdir = os.getcwd()
    if args.pull_id != None:
        pull_request()
    else:
        verify()

def get_parsed_args():
    parser = argparse.ArgumentParser(usage='%(prog)s [options]', description='Use this script to verify the signatures of existing gitian assert files and / or assert files in a specific pull request.')
    parser.add_argument('-p', '--pull_id', dest='pull_id', help='GitHub Pull request id to check')
    parser.add_argument('-r', '--remote', dest='remote', default='upstream', help='The git remote repository')
    parser.add_argument('-t', '--target-branch', dest='target_branch', default='master', help='Remote repository merge into branch')
    parser.add_argument('-m', '--merge', action='store_true', dest='merge', help='Merge the given pull request id')
    parser.add_argument('-k', '--refresh-keys', action='store_true', dest='refresh_keys', help='Refresh all public keys that are currently in the gpg keyring.')
    parser.add_argument('-i', '--import-keys', action='store_true', dest='import_keys', help='Import all public keys in the gitian-pubkeys directory to the gpg keyring.')
    parser.add_argument('-o', '--no-verify', action='store_true', dest='no_verify', help='Do not run any signature verification')
    parser.add_argument('-v', '--version', dest='version', help='Version number of sigs to be verified (defaults to all versions if not specified).')
    return parser.parse_args()

def pull_request():
    global args
    # Get branch from remote pull request and compare
    head_branch = args.pull_id + '_head'
    subprocess.check_call([GIT, 'fetch', args.remote])
    subprocess.check_call([GIT, 'checkout', args.remote + '/' + args.target_branch])
    subprocess.check_call([GIT, 'fetch', '-q', args.remote, 'pull/' + args.pull_id + '/head:' + head_branch])
    subprocess.check_call([GIT, 'checkout', '-f', head_branch])
    if args.merge:
        # Hard reset the target branch to the remote's state and merge the pull request's head branch into it
        subprocess.check_call([GIT, 'checkout', args.target_branch])
        subprocess.check_call([GIT, 'reset', '--hard', args.remote + '/' + args.target_branch])
        print('Merging and signing pull request #' + args.pull_id + ' , if you are using a smartcard, confirm the signature now.')
        subprocess.check_call([GIT, 'merge', '-q', '--commit', '--no-edit', '-m', 'Merge pull request #' + args.pull_id + ' into ' + args.target_branch, '--no-ff', '--gpg-sign', head_branch])
    if not args.no_verify:
        verify()
    subprocess.check_call([GIT, 'checkout', 'master'])
    subprocess.check_call([GIT, 'branch', '-D', head_branch])

def refresh_gpg_keys():
    print('Refreshing pubkeys...')
    subprocess.check_call([GPG, '--refresh'])

def import_gpg_keys():
    os.chdir(GITIAN_PUBKEYS_DIR)
    print('Importing gpg pubkeys...')
    keys = glob.glob('*.asc')
    for key in keys:
        subprocess.check_call([GPG, '--import', key])
    os.chdir('../')

def get_assert_file_list(ver_pattern):
    assert_files = []
    for assert_file in sorted(glob.glob(ver_pattern + '-*/*/*.assert')):
        pieces = assert_file.split('/')
        release_full = pieces[0] # eg v0.15.0.1-linux
        release_num, platform = release_full.split('-')
        version_major = release_num.split('.')[1]
        assert_files.append({
            'release_full': release_full,
            'release_num': release_num,
            'platform': platform,
            'path': assert_file,
            'user': pieces[1],
            'version_major': version_major})
    return assert_files

def verify_gpg_sigs(sig_file_paths):
    print('Verifying signatures:')
    is_verification_error = False
    for sig_file in sig_file_paths:
        print(' - ' + '{message: <{fill}}'.format(message=sig_file, fill='72'), end='')
        result = verify_gpg_sig(sig_file)
        if result.returncode != 0:
            is_verification_error = True
            print('\n')
            sys.stderr.write('ERROR:\n' + result.stderr + '-' * 80 + '\n')
        else:
            print(' [OK]')
    if is_verification_error:
        sys.stderr.write('ERROR: One or more signatures failed verification.\n')
        exit(1)
    print('All signatures verified correctly.\n')

def verify_file_path_naming(assert_files, sig_file_paths, user_names):
    path_pattern = '{release_num}-{platform}/{user}/monero-{platform}-0.{version_major}-build.assert'
    print('Verifying file path naming...')
    # Check that every sig has an assert:
    if len(sig_file_paths) > len(assert_files):
        sys.stderr.write("ERROR: One or more sig files doesn't have a matching assert file:\n")
        assert_file_paths = [a['path'] for a in assert_files]
        extra_sigs = [s for s in sig_file_paths if os.path.splitext(s)[0] not in assert_file_paths]
        for extra_sig in extra_sigs:
            sys.stderr.write("  - {0}\n".format(extra_sig))
        exit(1)
    for assert_file in assert_files:
        # Check assert file has a sig file:
        if (assert_file['path'] + '.sig') not in sig_file_paths:
            sys.stderr.write('ERROR: Assert file found without corresponding sig file:\n' + assert_file['path'] + '\n')
            exit(1)
        # Check assert user corresponds with a known GPG pubkey:
        if assert_file['user'] not in user_names:
            sys.stderr.write("ERROR: User '{user}' doesn't have a matching PGP key.  Expected {folder}/{user}.asc\n".format(user=assert_file['user'], folder=GITIAN_PUBKEYS_DIR))
            sys.stderr.write(" * Found in path: {path}\n".format(path=assert_file['path']))
            exit(1)
        # Check overall format of path (version num, platform, folder and file names):
        expected_path = path_pattern.format(**assert_file)
        if expected_path != assert_file['path']:
            sys.stderr.write('ERROR: File path appears to be incorrect:\n{actual}\nExpected:\n{expected}\n'.format(actual=assert_file['path'], expected=expected_path))
            exit(1)
    print('All file paths seem to be correct.\n')

def get_user_names_from_keys():
    os.chdir(GITIAN_PUBKEYS_DIR)
    user_names = [os.path.splitext(key)[0] for key in glob.glob('*.asc')]
    os.chdir('../')
    return user_names

def verify_gpg_sig(sig_file):
    # TODO: Verify correct user created the signature.
    return subprocess.run([GPG, '--verify', sig_file], capture_output=True, encoding='utf-8')

def verify_checksums(assert_files):
    print('Beginning binary checksum comparison...\n')
    # Check that the contents between the assertion signers match.
    # This is meant for quick verification, not for validation of their contents.
    # TODO: prevent false positives related to filenames / whitespace / formatting.
    prev_release_num = ''
    prev_release_full = ''
    prev_platform = ''
    for assert_file in assert_files:
        release_full = assert_file['release_full']
        if release_full != prev_release_full:
            first_user = assert_file['user']
            first_file = assert_file['path']
            prev_release_full = release_full
            if prev_release_num != assert_file['release_num']:
                print('  ' + assert_file['release_num'])
                prev_release_num = assert_file['release_num']
            f = open(first_file, 'r')
            first_file_contents = f.readlines()
            f.close()
            continue
        platform = assert_file['platform']
        if platform != prev_platform:
            prev_platform = platform
            print('      ' + platform)
            print('          ' + first_user)
        print('          ' + assert_file['user'])
        assert_file_handle = open(assert_file['path'], 'r')
        assert_file_contents = assert_file_handle.readlines()
        assert_file_handle.close()
        for i in range(len(assert_file_contents)):
            # Compare each line in the assertion file until base_manifests:
            if assert_file_contents[i] == '- base_manifests: !!omap\n':
                break
            # The OSX SDK may change from time to time:
            if 'sdk' in assert_file_contents[i]:
                continue
            if assert_file_contents[i] != first_file_contents[i]:
                sys.stderr.write('ERROR: Found conflicting contents on line: ' + str(i) + ' of file ')
                sys.stderr.write(assert_file['path'] + ':\n' + assert_file_contents[i])
                sys.stderr.write(first_file + ':\n' + first_file_contents[i])
                exit(1)
    print('No discrepancies found in assertion files.')

if __name__ == '__main__':
    main()
