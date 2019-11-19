#!/usr/bin/env python3
import argparse
import os
import subprocess
import glob
import sys

GIT = os.getenv('GIT','git')
GPG = os.getenv('GPG','gpg')

def verify():
    global args, workdir
    if args.import_keys:
        os.chdir('gitian-pubkeys')
        print('Importing gpg pubkeys...')
        keys = [f for f in glob.glob('*.asc', recursive=False)]
        for key in keys:
            subprocess.check_call([GPG, '--import', key])
        os.chdir('../')
    if args.refresh_keys:
        print('Refreshing pubkeys...')
        subprocess.check_call([GPG, '--refresh'])
    print('Verifying signatures:')
    is_verification_error = False
    ver_pattern = args.version if args.version else 'v0*'
    for sig_file in sorted(glob.glob(ver_pattern + '-*/*/*.sig', recursive=False)):
        print(' - ' + '{message: <{fill}}'.format(message=sig_file, fill='72'), end='')
        result = subprocess.run([GPG, '--verify', sig_file], capture_output=True, encoding='utf-8')
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
    print('Beginning checksum comparison...\n')
    # Check that the contents between the assertion signers match.
    # This is meant for quick verification, not for validation of their contents.
    # TODO: prevent false positives related to filenames / whitespace / formatting.
    builds = glob.glob(ver_pattern + '*')
    for build in builds:
        first_file = glob.glob(build + '/*/*.assert', recursive=False)[0]
        f = open(first_file, 'r')
        first_file_contents = f.readlines()
        f.close()
        for assert_file in glob.glob(build + '/*/*.assert', recursive=False):
            f = open(assert_file, 'r')
            assert_file_contents = f.readlines()
            f.close()
            for i in range(len(assert_file_contents)):
                # Compare each line in the assertion file until base_manifests:
                if assert_file_contents[i] == '- base_manifests: !!omap\n':
                    break
                # The OSX SDK may change from time to time:
                if 'sdk' in assert_file_contents[i]:
                    continue
                if assert_file_contents[i] != first_file_contents[i]:
                    sys.stderr.write('ERROR: Found conflicting contents on line:', i)
                    sys.stderr.write(assert_file + ':\n' + assert_file_contents[i])
                    sys.stderr.write(first_file + ':\n' + first_file_contents[i])
                    exit(1)

    print('No discrepancies found in assertion files.')
    print('All checks passed.')
    os.chdir(workdir)

def main():
    host_repo = 'git@github.com/monero-project/gitian.sigs'
    global args, workdir
    parser = argparse.ArgumentParser(usage='%(prog)s [options]', description='Use this script to verify the signatures of existing gitian assert files and / or assert files in a specific pull request.')
    parser.add_argument('-p', '--pull_id', dest='pull_id', help='GitHub Pull request id to check')
    parser.add_argument('-r', '--remote', dest='remote', default='upstream', help='The git remote repository')
    parser.add_argument('-t', '--target-branch', dest='target_branch', default='master', help='Remote repository merge into branch')
    parser.add_argument('-m', '--merge', action='store_true', dest='merge', help='Merge the given pull request id')
    parser.add_argument('-k', '--refresh-keys', action='store_true', dest='refresh_keys', help='Refresh all public keys that are currently in the gpg keyring.')
    parser.add_argument('-i', '--import-keys', action='store_true', dest='import_keys', help='Import all public keys in the gitian-pubkeys directory to the gpg keyring.')
    parser.add_argument('-o', '--no-verify', action='store_true', dest='no_verify', help='Do not run any signature verification')
    parser.add_argument('-v', '--version', dest='version', help='Version number of sigs to be verified (defaults to all versions if not specified).')

    args = parser.parse_args()

    workdir = os.getcwd()
    if args.pull_id != None:
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
    else:
        verify()


if __name__ == '__main__':
    main()
