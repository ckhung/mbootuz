#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse, re, sys, subprocess, math, time, os, warnings, atexit, glob
from shutil import copy2 

def wipe(args):
    if args.dryrun:
        sys.exit('the wipe subcommand does not support dryrun mode')
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
        communicate(input=fdisk_cmds.encode())
    subprocess.call(['mkfs', '-t', 'vfat', args.TARGET+'1'])

def cleanup(mount_point):
    subprocess.call(['sync'])
    subprocess.call(['umount', mount_point])
    subprocess.call(['rmdir', mount_point])

def mounted_at(dev='', loopback=''):
    df = subprocess.check_output(['df']).decode("utf-8")
    if dev:
        fn = dev[dev.rfind('/')+1:]
        dev_or_loop = dev
        m = re.search('^' + dev + r'\s.*\s(\S+)$', df, flags=re.MULTILINE)
    elif loopback:
        dev_or_loop = loopback
        fn = loopback[loopback.rfind('/')+1:]
        m = re.search(r'\s(/lib/live/\S*' + fn + ')$', df, flags=re.MULTILINE)
    else:
        sys.exit('mounted_at() needs at least one arg')
    if (m):
        return m.group(1)
    else:
        target_mp = '/tmp/mbootuz-' + str(os.getpid()) + '-' + fn
        subprocess.call(['mkdir', target_mp])
        try:
            subprocess.check_output(['mount', dev_or_loop, target_mp])
        except subprocess.CalledProcessError as e:
            subprocess.call(['rmdir', target_mp])
            sys.exit('mount failure [' + e.output.decode("utf-8") +
                '], mbootuz aborted')
        atexit.register(cleanup, target_mp)
        return target_mp

def mkboot(args):
    if args.dryrun:
        sys.exit('the mkboot subcommand does not support dryrun mode')
    tdev = args.TARGET
    try:
        subprocess.check_output(['ls', args.TARGET+'1'])
        tdev += '1'
        subprocess.call(['dd', 'bs=440', 'count=1',
            'if=/usr/lib/syslinux/mbr/mbr.bin', 'of='+args.TARGET])
        time.sleep(1)
        tmp = subprocess.check_output(['fdisk', '-l', args.TARGET]).decode("utf-8")
        if not re.search(tdev + r'\b', tmp):
            sys.exit('unexpected error: no entry for ' + tdev + ' in `fdisk -l`')
        if not re.search(tdev + r'\s+\*', tmp):
            # partition was not set active
            print('using fdisk to activate ' + tdev)
            subprocess.Popen(['fdisk', args.TARGET], stdin=subprocess.PIPE). \
                communicate(input=b'a\n1\nw\n')
    except subprocess.CalledProcessError as e:
        warnings.warn(args.TARGET +
            ' is not partitioned? using whole disk as one big file system')
    target_mp = mounted_at(tdev)
    subprocess.call(['mkdir', '-p', target_mp+'/boot'])
    subprocess.call(['cp', '-r', '--preserve=mode,timestamps', '/usr/lib/syslinux', target_mp+'/boot'])
    subprocess.call(['extlinux', '-i', target_mp+'/boot/syslinux'])

def find_files(path, pattern):
    n = len(path)
    r = subprocess.check_output(['find', path, '-name', pattern]).decode("utf-8").split('\n')
    r = [x[n:].lstrip('/') for x in r]
    return [x for x in r if x]

def find_boot_files(name, shortname, basedir):
# find vmlinuz or initrd
    if name:
        fullpath = name if name[0]=='/' else basedir + '/boot/' + name
    else:
        # try the (only) symlink at the root directory
        try1 = basedir + '/' + shortname + '*'
        found = sorted(glob.glob(try1))
        if len(found) >= 1 and os.access(found[0], os.R_OK):
            fullpath = os.path.realpath(found[0])
        else:
            # try the highest numbered version at /boot
            try2 = basedir + '/boot/' + shortname + '*'
            found = sorted(glob.glob(try2))
            if len(found) < 1:
                sys.exit('cannot read ' + try1 + ' and cannot find ' + try2)
            fullpath = found[-1]
            if (len(found) > 1):
                warnings.warn('found more than one ' + try2 + ' , using ' + fullpath)
    if not os.access(fullpath, os.R_OK):
        sys.exit('failed to read ' + fullpath)
    return fullpath

def mklive(args):
    sys.exit('the subcommand "mklive" has been replaced by "cplive", with different options. "mbootuz.py -h" to see help')

def cplive(args):
    tdev = args.TARGET
    try:
        subprocess.check_output(['ls', tdev+'1']).decode("utf-8")
        tdev += '1'
    except subprocess.CalledProcessError as e:
        warnings.warn(args.TARGET +
            ' is not partitioned? using whole disk as one big file system')

    df = ''
    if not args.squashfs :
        df = subprocess.check_output(['df']).decode("utf-8").split('\n')
        line = next((line for line in df if re.search(r'/lib/live/', line)), '')
        m = re.search(r'(/lib/live/\S+)', line)
        if not m:
            sys.exit('--squashfs is empty and "df" finds no /lib/live/...')
        args.squashfs = m.group(1)
    if re.search(r'\.squashfs$', args.squashfs):
        # the mount point name ends in .squashfs => we were booted toram, files in iso are inaccessible, the squashfs image will have to be accessed using dd
        sq_mp = args.squashfs
    else:
        if os.path.isdir(args.squashfs):
            squashfs_list = find_files(args.squashfs, '*\.squashfs')
            if not squashfs_list:
                sys.exit('cannot find *.squashfs under '+args.squashfs)
            if len(squashfs_list) > 1:
                warnings.warn('found more than one squashfs')
            args.squashfs += '/' + squashfs_list[0]
            print('using ' + args.squashfs + ' as rootfs')
        # https://stackoverflow.com/questions/32073498/check-if-file-is-readable-with-python-try-or-if-else
        sq_mp = mounted_at(loopback=args.squashfs)
    sq_bn = args.squashfs[args.squashfs.rfind('/')+1:]

    kernel_fp = find_boot_files(args.kernel, 'vmlinuz', sq_mp)
    args.kernel = kernel_fp[kernel_fp.rfind('/')+1:]
    initrd_fp = find_boot_files(args.initrd, 'initrd', sq_mp)
    args.initrd = initrd_fp[initrd_fp.rfind('/')+1:]

    target_mp = mounted_at(tdev)
    if args.dest_dir[0] != '/':
        args.dest_dir = '/' + args.dest_dir
    dst = target_mp + args.dest_dir
    if dst[-1] != '/':
        dst += '/'
    subprocess.call(['mkdir', '-p', dst])
    for f in [kernel_fp, initrd_fp]:
        print('copying '+f+' to '+dst+' ...')
        if not args.dryrun:
            copy2(f, dst)
    if sq_mp == args.squashfs:
        print("dd'ing /dev/loop0 to "+dst+" as "+ sq_bn)
        if not args.dryrun:
            subprocess.call(['dd', 'if=/dev/loop0', 'of='+dst+'/'+sq_bn])
    else:
        print('copying '+args.squashfs+' to '+dst+' ...')
        if not args.dryrun:
            copy2(args.squashfs, dst)

    cfg_entry = '''
label {dest}-toram-{lid}
        menu label {dest} linux live CD {lid} boot to ram!
        kernel /{dest}/{kernel}
        append initrd=/{dest}/{initrd} boot=live live-media-path=/{dest} toram={squashfs}
'''
    if args.profile:
        cfg_entry += '''
label {dest}-persistence-{lid}
        menu label {dest} linux live CD {lid} w/ persistence
        kernel /{dest}/{kernel}
        append initrd=/{dest}/{initrd} boot=live live-media-path=/{dest} persistence persistence-path=/{dest} persistence-label={prof}
'''
    cfg_entry = cfg_entry.format(
        lid=str(os.getpid()),
        dest=args.dest_dir[1:],
        kernel=args.kernel,
        initrd=args.initrd,
        squashfs=sq_bn,
        prof=args.profile
    )
    cfg_entry = re.sub(r'/{2,}', '/', cfg_entry)
    if not args.dryrun:
        with open(target_mp+'/boot/syslinux/extlinux.conf', 'a') as cfg_file:
            cfg_file.write(cfg_entry)
    else:
        print(cfg_entry)

    if args.profile:
        pmd = '/tmp/mbootuz-' + str(os.getpid()) + '-pers'
        pimg = target_mp + args.dest_dir + '/' +args.profile
        cmds='''
dd count={size} bs=1048576 < /dev/zero > {pimg}
mkfs -t ext4 {pimg}
mkdir {pmd}
mount {pimg} {pmd}
echo '/ union' > {pmd}/persistence.conf
sync
umount {pmd}
rmdir {pmd}
'''.format(size=args.persize, pimg=pimg, pmd=pmd)
        print('creating persistence image file '+pimg+' ...')
        if not args.dryrun:
            subprocess.call(cmds, shell=True)

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
        'mklive': mklive,
        'cplive': cplive,
    },
}

parser = argparse.ArgumentParser(
    description='make a bootable usb drive, possibly with zfs',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('SUBCMD', help='valid subcommands: '+','.join(G['subcmds']))
parser.add_argument('-d', '--dest_dir', type=str,
    default='/mblcd', help='dest dir relative to root of TARGET partition')
parser.add_argument('-L', '--size', type=str,
    default='12G', help='size for linux partition')
# https://stackoverflow.com/questions/9183936/boolean-argument-for-script
parser.add_argument('-n', '--dryrun', action='store_true',
    default=False, help='do not actually copy files (only for cplive)')
parser.add_argument('-o', '--options', type=str,
    default='', help='special options such as force_sda')
parser.add_argument('-p', '--profile', type=str,
    default='', help='name of persistence profile')
parser.add_argument('-t', '--type', type=str,
    default='bf', help='type of linux partition ("bf" for zfs or "83" for ext2/3/4)')
parser.add_argument('-x', '--max', type=str,
    default='80G', help='max allowed size of TARGET device')
parser.add_argument('-Z', '--persize', type=str,
    default='512M', help='size of persistence file')
parser.add_argument('--kernel', type=str,
    default='', help='file name (relative to /boot in *.squashfs) of kernel')
parser.add_argument('--initrd', type=str,
    default='', help='file name (relative to /boot in *.squashfs) of initrd')
parser.add_argument('-q', '--squashfs', type=str,
    default='', help='search directory or full path of the root squashfs image')
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
args.persize = normalize_size(args.persize)
args.max = normalize_size(args.max)
G['dev_size'] = normalize_size(
    subprocess.check_output(['fdisk', '-s', args.TARGET]).decode("utf-8").strip()+'K')

G['subcmds'][args.SUBCMD](args)

