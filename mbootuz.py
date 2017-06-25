#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse, re, sys, subprocess, math, time, os

# import argparse, sys, math, warnings

def wipe(args):
    # sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | fdisk $TARGET
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
    fdisk_cmds = re.sub('^[ \t]*', '', re.sub(' *#.*', '', fdisk_cmds[1:-1]), flags=re.MULTILINE)
    subprocess.Popen(['fdisk', args.TARGET], stdin=subprocess.PIPE).communicate(input=fdisk_cmds)
    subprocess.call(['mkfs', '-t', 'vfat', args.TARGET+'1'])

def mkboot(args):
    subprocess.call(['dd', 'bs=440', 'count=1', 'if=/usr/lib/syslinux/mbr/mbr.bin', 'of='+args.TARGET])
    re.search(args.TARGET+'1.*(\W+)$', subprocess.check_output(['df']))
    m = re.search(args.TARGET+'1.*\s(\S+)$', subprocess.check_output(['df']))
    if (m):
        mount_dir = m.group(1)
        need_umount = False
    else:
        time.sleep(1)
        mount_dir = '/tmp/mbootuz-' + str(os.getpid())
        subprocess.call(['mkdir', mount_dir])
        subprocess.call(['mount', args.TARGET+'1', mount_dir])
        need_umount = True
    # print 'Copying may take a few minutes. Be patient.'
    # subprocess.call(['cp', '-pr', '/usr/lib/mbootuz/boot', mount_dir])
    subprocess.call(['mkdir', mount_dir+'/boot'])
    subprocess.call(['cp', '-pr', '/usr/lib/syslinux', mount_dir+'/boot'])
    subprocess.call(['extlinux', '-i', mount_dir+'/boot/syslinux'])
    if need_umount:
        subprocess.call(['umount', args.TARGET+'1'])
        subprocess.call(['rmdir', mount_dir])

def normalize_size(s):
    if (re.search('^\d+k$', s, flags=re.IGNORECASE)):
        return float(s[:-1])/1024
    if (re.search('^\d+m$', s, flags=re.IGNORECASE)):
        return float(s[:-1])
    if (re.search('^\d+g$', s, flags=re.IGNORECASE)):
        return float(s[:-1])*1024
    raise ValueError('this string does not describe a size: ' + s)

G = {
    'dev_size': 0,
    'subcmds': {
        'wipe': wipe,
        'mkboot': mkboot,
    },
}

parser = argparse.ArgumentParser(description='make a bootable usb drive with zfs',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
if not re.search('^/dev/sd[b-z]$', args.TARGET):
    sys.exit('error: I only accept /dev/sdb ... /dev/sdz as TARGET')

args.size = normalize_size(args.size)
args.max = normalize_size(args.max)
G['dev_size'] = normalize_size(subprocess.check_output(['fdisk', '-s', args.TARGET]).strip()+'K')

if G['dev_size'] > args.max:
    sys.exit('error: I only process devices of size < ' + str(args.max) + 'M')
if args.size > G['dev_size']:
    sys.exit('error: requested size ' + str(args.size) + 'M exceeds device size ' + str(G['dev_size']) + 'M')

G['subcmds'][args.SUBCMD](args)

