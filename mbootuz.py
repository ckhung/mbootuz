#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse, re, sys, subprocess, math, time, os, warnings

# import argparse, sys, math, warnings

def wipe(args):
    if G['dev_size'] > args.max:
        sys.exit('error: I only process devices of size < ' + str(args.max) + 'M')
    if args.size > G['dev_size']:
        sys.exit('error: requested size ' + str(args.size) +
        'M exceeds device size ' + str(G['dev_size']) + 'M')

    # https://superuser.com/questions/332252/creating-and-formating-a-partition-using-a-bash-script
    fdisk_cmds = '''
        o # create a new empty DOS partition table
        n # new partition
        p # primary partition
        1 # partition number 1
          # default - start at beginning of disk 
        +%dM # vfat parttion
        n # new partition
        p # primary partition
        2 # partion number 2
          # default, start immediately after preceding partition
          # default, extend partition to end of disk
        a # make a partition bootable
        1 # bootable partition is partition 1
        t # set partition type
        1 # of partition 1
        c # to "W95 FAT32 (LBA)"
        t # set partition type
        2 # of partition 2
        %s # to solaris (zfs) or linux (ext2/3/4)
        w # write the partition table
''' % (int(math.ceil(G['dev_size']-args.size)), args.type)
    fdisk_cmds = re.sub(r'^[ \t]*', '', re.sub(r' *#.*', '',
        fdisk_cmds[1:-1]), flags=re.MULTILINE)
    subprocess.Popen(['fdisk', args.TARGET], stdin=subprocess.PIPE). \
        communicate(input=fdisk_cmds)
    subprocess.call(['mkfs', '-t', 'vfat', args.TARGET+'1'])

def mkboot(args):
    dev = args.TARGET
    try:
        subprocess.check_output(['ls', args.TARGET+'1'])
        dev += '1'
        subprocess.call(['dd', 'bs=440', 'count=1',
            'if=/usr/lib/syslinux/mbr/mbr.bin', 'of='+args.TARGET])
        time.sleep(1)
        tmp = subprocess.check_output(['fdisk', '-l', args.TARGET])
        if not re.search(dev + r'\b', tmp):
            sys.exit('unexpected error: no entry for ' + dev + ' in `fdisk -l`')
        if not re.search(dev + r'\s+\*', tmp):
            # partition was not set active
            print 'using fdisk to activate ' + dev
            subprocess.Popen(['fdisk', args.TARGET], stdin=subprocess.PIPE). \
                communicate(input='a\n1\nw\n')
    except subprocess.CalledProcessError as e:
        warnings.warn(args.TARGET +
            ' is not partitioned? using whole disk as one big file system')
    m = re.search(dev + r'\b.*\s(\S+)$',
        subprocess.check_output(['df']), flags=re.MULTILINE)
    if (m):
        mount_dir = m.group(1)
        need_umount = False
    else:
        mount_dir = '/tmp/mbootuz-' + str(os.getpid())
        subprocess.call(['mkdir', mount_dir])
        try:
            subprocess.check_output(['mount', dev, mount_dir])
        except subprocess.CalledProcessError as e:
            subprocess.call(['rmdir', mount_dir])
            sys.exit('mount failure [' + e.output +
                '], boot loader installation aborted')
        need_umount = True
    subprocess.call(['mkdir', '-p', mount_dir+'/boot'])
    subprocess.call(['cp', '-pr', '/usr/lib/syslinux', mount_dir+'/boot'])
    subprocess.call(['extlinux', '-i', mount_dir+'/boot/syslinux'])
    if need_umount:
        subprocess.call(['umount', dev])
        subprocess.call(['rmdir', mount_dir])

def normalize_size(s):
    if (re.search(r'^\d+k$', s, flags=re.IGNORECASE)):
        return float(s[:-1])/1024
    if (re.search(r'^\d+m$', s, flags=re.IGNORECASE)):
        return float(s[:-1])
    if (re.search(r'^\d+g$', s, flags=re.IGNORECASE)):
        return float(s[:-1])*1024
    raise ValueError('this string does not describe a size: ' + s)

G = {
    'dev_size': 0,
    'subcmds': {
        'wipe': wipe,
        'mkboot': mkboot,
    },
}

parser = argparse.ArgumentParser(
    description='make a bootable usb drive with zfs',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('SUBCMD', help='valid subcommands: wipe, mkboot')
parser.add_argument('-L', '--size', type=str,
    default='12G', help='size for linux partition')
parser.add_argument('-x', '--max', type=str,
    default='80G', help='max allowed size of TARGET device')
parser.add_argument('-t', '--type', type=str,
    default='bf', help='type of linux partition ("bf" for zfs or "83" for ext2/3/4)')
parser.add_argument('TARGET', help='target device, e.g. /dev/sdz')
args = parser.parse_args()

if not args.SUBCMD in G['subcmds']:
    sys.exit('error: valid subcommands: wipe, mkboot')
if not re.search(r'^/dev/sd[b-z]$', args.TARGET):
    sys.exit('error: I only accept /dev/sdb ... /dev/sdz as TARGET')

args.size = normalize_size(args.size)
args.max = normalize_size(args.max)
G['dev_size'] = normalize_size(
    subprocess.check_output(['fdisk', '-s', args.TARGET]).strip()+'K')

G['subcmds'][args.SUBCMD](args)

