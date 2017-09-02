#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse, re, sys, subprocess, math, time, os, warnings, glob
from shutil import copy2 

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
        +{vsize}M # vfat parttion
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
        {ptype} # to solaris (zfs) or linux (ext2/3/4)
        w # write the partition table
'''.format(vsize=int(math.ceil(G['dev_size']-args.size)), ptype=args.type)
    fdisk_cmds = re.sub(r'^[ \t]*', '', re.sub(r' *#.*', '',
        fdisk_cmds[1:-1]), flags=re.MULTILINE)
    subprocess.Popen(['fdisk', args.TARGET], stdin=subprocess.PIPE). \
        communicate(input=fdisk_cmds)
    subprocess.call(['mkfs', '-t', 'vfat', args.TARGET+'1'])

def mounted_at(dev):
    m = re.search(dev + r'\b.*\s(\S+)$',
        subprocess.check_output(['df']), flags=re.MULTILINE)
    if (m):
        mount_dir = m.group(1)
	return (mount_dir, False)
    else:
        mount_dir = '/tmp/mbootuz-' + str(os.getpid())
        subprocess.call(['mkdir', mount_dir])
        try:
            subprocess.check_output(['mount', dev, mount_dir])
        except subprocess.CalledProcessError as e:
            subprocess.call(['rmdir', mount_dir])
            sys.exit('mount failure [' + e.output +
                '], mbootuz aborted')
        return (mount_dir, True)

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
    (mount_dir, need_umount) = mounted_at(dev)
    subprocess.call(['mkdir', '-p', mount_dir+'/boot'])
    subprocess.call(['cp', '-pr', '/usr/lib/syslinux', mount_dir+'/boot'])
    subprocess.call(['extlinux', '-i', mount_dir+'/boot/syslinux'])
    if need_umount:
        subprocess.call(['sync'])
        subprocess.call(['umount', dev])
        subprocess.call(['rmdir', mount_dir])

def live(args):
    dev = args.TARGET
    try:
        subprocess.check_output(['ls', dev+'1'])
        dev += '1'
    except subprocess.CalledProcessError as e:
        warnings.warn(args.TARGET +
            ' is not partitioned? using whole disk as one big file system')
    kernel_list = glob.glob(args.iso_mount_dir+'/vmlinuz*')
    if not kernel_list:
	sys.exit('cannot find vmlinuz* in ' + args.iso_mount_dir)
    initrd_list = glob.glob(args.iso_mount_dir+'/initrd*')
    if not initrd_list:
	sys.exit('cannot find initrd* in ' + args.iso_mount_dir)
    (mount_dir, need_umount) = mounted_at(dev)
    subprocess.call(['mkdir', '-p', mount_dir+args.dest_dir])
    for f in kernel_list + initrd_list:
	copy2(f, mount_dir+args.dest_dir)
    if args.squashfs:
	for f in glob.glob(args.squashfs):
	    copy2(f, mount_dir+args.dest_dir)
    # copy2(mount_dir+'/boot/syslinux/modules/bios/ldlinux.c32', mount_dir+'/boot/syslinux/')
    # unlike isolinux.cfg, extlinux.conf does not need ldlinux.c32 to be at the same dir
    with open(mount_dir+'/boot/syslinux/extlinux.conf', 'a') as cfg_file:
	n = len(args.iso_mount_dir)
	cfg_entry = '''
label live-cd-persistence
	menu label Live CD w/ persistence
	kernel {dest}/{kernel}
	append initrd={dest}/{initrd} boot=live live-media-path={dest} persistence persistence-path={dest} persistence-label=stux.img
'''.format(
	    dest=args.dest_dir,
	    kernel=glob.glob(args.iso_mount_dir+'/vmlinuz*')[0][n+1:],
	    initrd=glob.glob(args.iso_mount_dir+'/initrd*')[0][n+1:],
	)
	cfg_file.write(cfg_entry)
    pmd = '/tmp/mbootuz-' + str(os.getpid()) + '-pers'
    pimg = mount_dir+args.dest_dir+'/stux.img'
    cmds='''
dd count={size} bs=1048576 < /dev/zero > {pimg}
mkfs -t ext4 {pimg}
mkdir {pmd}
mount {pimg} {pmd}
echo '/ union' > {pmd}/persistence.conf
sync
umount {pmd}
rmdir {pmd}
'''.format(size=args.persistence, pimg=pimg, pmd=pmd)
    subprocess.call(cmds, shell=True)
    if need_umount:
        subprocess.call(['sync'])
        subprocess.call(['umount', dev])
        subprocess.call(['rmdir', mount_dir])

def normalize_size(s):
    if (re.search(r'^\d+k$', s, flags=re.IGNORECASE)):
        return int(float(s[:-1])/1024)
    if (re.search(r'^\d+m$', s, flags=re.IGNORECASE)):
        return int(float(s[:-1]))
    if (re.search(r'^\d+g$', s, flags=re.IGNORECASE)):
        return int(float(s[:-1])*1024)
    raise ValueError('this string does not describe a size: ' + s)

G = {
    'dev_size': 0,
    'subcmds': {
        'wipe': wipe,
        'mkboot': mkboot,
	'live': live,
    },
}

parser = argparse.ArgumentParser(
    description='make a bootable usb drive with zfs',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('SUBCMD', help='valid subcommands: '+','.join(G['subcmds']))
parser.add_argument('-d', '--dest_dir', type=str,
    default='/mblcd', help='dest dir relative to root of TARGET partition')
parser.add_argument('-i', '--iso_mount_dir', type=str,
    default='/lib/live/mount/medium', help='mount point of the (source) live-boot iso')
parser.add_argument('-L', '--size', type=str,
    default='12G', help='size for linux partition')
parser.add_argument('-o', '--options', type=str,
    default='', help='special options such as force_sda')
parser.add_argument('-p', '--persistence', type=str,
    default='512M', help='size of persistence file')
parser.add_argument('-q', '--squashfs', type=str,
    default='/lib/live/mount/medium/live/*.squashfs', help='path of source squashfs')
parser.add_argument('-t', '--type', type=str,
    default='bf', help='type of linux partition ("bf" for zfs or "83" for ext2/3/4)')
parser.add_argument('-x', '--max', type=str,
    default='80G', help='max allowed size of TARGET device')
parser.add_argument('TARGET', help='target device, e.g. /dev/sdz')
args = parser.parse_args()

if not args.SUBCMD in G['subcmds']:
    sys.exit('error: valid subcommands: '+','.join(G['subcmds']))

if args.TARGET == '/dev/sda':
    if not 'force_sda' in args.options:
	sys.exit('use -o force_sda to enable /dev/sda as TARGET')
else:
    if not re.search(r'^/dev/sd[b-z]$', args.TARGET):
	sys.exit('error: I only accept /dev/sda ... /dev/sdz as TARGET')

args.size = normalize_size(args.size)
args.persistence = normalize_size(args.persistence)
args.max = normalize_size(args.max)
G['dev_size'] = normalize_size(
    subprocess.check_output(['fdisk', '-s', args.TARGET]).strip()+'K')

G['subcmds'][args.SUBCMD](args)

