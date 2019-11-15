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
    if not os.path.isdir(args.gitian_builder_dir):
        sys.stderr.write('Please clone the gitian-builder repository from github.com/devrandom/gitian-builder to the directory containing the gitian.sigs repository.\nIf you already have the gitian.sigs directory cloned, but under another name or path, use --gitian-builder-dir to pass its absolute directory path to the script.\n')
        sys.exit(1)
    if not os.path.isdir(args.monero_dir):
        sys.stderr.write('Please clone the monero repository from github.com/monero-project/monero to the directory containing the gitian.sigs repository.\nIf you already have the monero repository cloned, but under another name or path, use --monero-dir to pass its absolute directory path to the script.\n')
        sys.exit(1)
    os.chdir(args.gitian_builder_dir)
    for os_label, os_id in [("Linux","linux"), ("Windows","win"), ("MacOS","osx"), ("Android", "android")]:
        if os.path.isdir(workdir + '/' + args.version + '-' + os_id):
            print('\nVerifying ' + args.version + ' ' + os_label)
            subprocess.check_call(['bin/gverify', '-v', '-d', workdir, '-r', args.version + '-' + os_id, args.monero_dir + '/contrib/gitian/gitian-' + os_id + '.yml'])
    os.chdir(workdir)

def main():
    host_repo = "git@github.com/monero-project/gitian.sigs"
    global args, workdir
    parser = argparse.ArgumentParser(usage='%(prog)s [options] version', description='Use this script before merging a pull request to the gitian.sigs repository and to verify the signature of existing gitian assert files and gitian assert files in specific pull requests')
    parser.add_argument('-p', '--pull_id', dest='pull_id', help='Github Pull request id to check')
    parser.add_argument('--monero-dir', dest='monero_dir', default='../monero', help='System Path to the monero repository, e.g. /home/user/monero')
    parser.add_argument('--gitiian-builder-dir', dest='gitian_builder_dir', default='../gitian-builder', help='System Path to the gitian-builder repository, e.g. /home/user/gitian-builder')
    parser.add_argument('-r', '--remote', dest='remote', default='upstream', help='git remote repository')
    parser.add_argument('-t', '--target-branch', dest='target_branch', default='master', help='Remote repository merge into branch')
    parser.add_argument('-m', '--merge', action='store_true', dest='merge', help='Merge the given pull request id')
    parser.add_argument('-k', '--refresh-keys', action='store_true', dest='refresh_keys', help='refresh all pgp public keys that are currently in the gpg keyring.')
    parser.add_argument('-i', '--import-keys', action='store_true', dest='import_keys', help='import all public keys in the gitian-pubkeys directory to the gpg keyring.')
    parser.add_argument('-o', '--no-verify', action='store_true', dest='no_verify', help='Do not run any signature verification')
    parser.add_argument('-n', '--name', dest='name', help='username for pgp key verification')
    parser.add_argument('version', help='Version number, commit, or branch to build.')

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
