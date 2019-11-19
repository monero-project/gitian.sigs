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
        print('Importing pubkeys...')
        keys = [f for f in glob.glob("*.asc", recursive=True)]
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

    os.chdir(workdir)

def main():
    host_repo = "git@github.com/monero-project/gitian.sigs"
    global args, workdir
    parser = argparse.ArgumentParser(usage='%(prog)s [options]', description='Use this script to verify the signatures of existing gitian assert files and / or assert files in a specific pull request.')
    parser.add_argument('-p', '--pull_id', dest='pull_id', help='Github Pull request id to check')
    parser.add_argument('-r', '--remote', dest='remote', default='upstream', help='git remote repository')
    parser.add_argument('-t', '--target-branch', dest='target_branch', default='master', help='Remote repository merge into branch')
    parser.add_argument('-m', '--merge', action='store_true', dest='merge', help='Merge the given pull request id')
    parser.add_argument('-k', '--refresh-keys', action='store_true', dest='refresh_keys', help='refresh all pgp public keys that are currently in the gpg keyring.')
    parser.add_argument('-i', '--import-keys', action='store_true', dest='import_keys', help='import all public keys in the gitian-pubkeys directory to the gpg keyring.')
    parser.add_argument('-o', '--no-verify', action='store_true', dest='no_verify', help='Do not run any signature verification')
    parser.add_argument('-v', '--version', dest='version', help='Version number of sigs to be verified (defaults to all versions if not specified).')

    args = parser.parse_args()

    workdir = os.getcwd()
    if args.pull_id != None:
        # Get branch from remote pull request and compare
        head_branch = args.pull_id+'_head'

        subprocess.check_call([GIT, 'fetch', args.remote])
        subprocess.check_call([GIT, 'checkout', args.remote+'/'+args.target_branch])
        subprocess.check_call([GIT, 'fetch','-q', args.remote, 'pull/'+args.pull_id+'/head:'+head_branch])
        subprocess.check_call([GIT, 'checkout', '-f', head_branch])
        if args.merge:
            # Hard reset the target branch to the remote's state and merge the pull request's head branch into it
            subprocess.check_call([GIT, 'checkout', args.target_branch])
            subprocess.check_call([GIT, 'reset', '--hard', args.remote + '/' + args.target_branch])
            print('Merging and signing pull request #' + args.pull_id + ' , if you are using a smartcard, confirm the signature now.')
            subprocess.check_call([GIT, 'merge','-q', '--commit', '--no-edit', '-m', 'Merge pull request #'+args.pull_id+' into '+args.target_branch, '--no-ff', '--gpg-sign', head_branch])
        if not args.no_verify:
            verify()
        subprocess.check_call([GIT, 'checkout', 'master'])
        subprocess.check_call([GIT, 'branch', '-D', head_branch])
    else:
        verify()


if __name__ == '__main__':
    main()
