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
    assert_files = get_assert_file_list()
    verify_gpg_sigs(assert_files)
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
    keys = [f for f in glob.glob('*.asc', recursive=False)]
    for key in keys:
        subprocess.check_call([GPG, '--import', key])
    os.chdir('../')

def get_assert_file_list():
    global args
    # Shell glob pattern for specific version or all builds:
    ver_pattern = args.version if args.version else 'v0*'
    assert_files = []
    for assert_file in sorted(glob.glob(ver_pattern + '-*/*/*.assert')):
        pieces = assert_file.split('/')
        release_full = pieces[0] # eg v0.15.0.1-linux
        release_num, platform = release_full.split('-')
        assert_files.append({
            'release_full': release_full,
            'release_num': release_num,
            'platform': platform,
            'path': assert_file,
            'user': pieces[1]})
    return assert_files

def verify_gpg_sigs(assert_files):
    print('Verifying signatures:')
    is_verification_error = False
    for assert_file in assert_files:
        sig_file = assert_file['path'] + '.sig'
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

def verify_gpg_sig(sig_file):
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
