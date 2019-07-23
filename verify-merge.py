#!/usr/bin/env python3
import argparse
import os
import subprocess
import glob

GIT = os.getenv('GIT','git')
GPG = os.getenv('GPG','gpg')

def verify():
    global args, workdir
    os.chdir('gitian-pubkeys')
    print('Importing pubkeys...')
    keys = [f for f in glob.glob("*.asc", recursive=True)]
    for key in keys:
        subprocess.check_call([GPG, '--import', key])
    print('Refreshing pubkeys...')
    subprocess.check_call([GPG, '--refresh'])
    os.chdir('../../gitian-builder')
    print('\nVerifying '+args.version+' Linux\n')
    subprocess.check_call(['bin/gverify', '-v', '-d', '../gitian.sigs/', '-r', args.version+'-linux', '../monero/contrib/gitian/gitian-linux.yml'])
    print('\nVerifying '+args.version+' Windows\n')
    subprocess.check_call(['bin/gverify', '-v', '-d', '../gitian.sigs/', '-r', args.version+'-win', '../monero/contrib/gitian/gitian-win.yml'])
    print('\nVerifying '+args.version+' MacOS\n')
    subprocess.check_call(['bin/gverify', '-v', '-d', '../gitian.sigs/', '-r', args.version+'-osx', '../monero/contrib/gitian/gitian-osx.yml'])
    os.chdir(workdir)

def main():
    host_repo = "git@github.com/monero-project/gitian.sigs"
    global args, workdir
    parser = argparse.ArgumentParser(usage='%(prog)s [options] version', description='Use this script before merging a pull request to the gitian.sigs repository and to verify the signature of existing gitian assert files and gitian assert files in specific pull requests')
    parser.add_argument('-p', '--pull_id', dest='pull_id', help='Github Pull request id to check')
    parser.add_argument('-r', '--remote', dest='remote', default='upstream', help='git remote repository')
    parser.add_argument('-t', '--target_branch', dest='target_branch', default='master', help='Remote repository merge into branch')
    parser.add_argument('-m', '--merge', action='store_true', dest='merge', help='Merge the given pull request id')
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
