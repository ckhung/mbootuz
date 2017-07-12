# mbootuz

mbootuz makes it easier for sys admins to write simple shell scripts
for creating bootable usb flash drive (usb stick).

mbootuz 的目標是要讓系統管理員可以寫簡單的 shell scripts 來建立開機隨身碟。

## Introduction

```mbootuz.py``` has two subcommands:
- ```wipe``` wipes/deletes/kills/destroys all data on the target usb drive,
  creates one vfat partition and one linux partition,
  makes the vfat partition bootable and formats it.
- ```mkboot``` installs mbr into the target usb drive,
  copies /usr/lib/syslinux into the /boot directory of the vfat partition,
  and installs extlinux into this new /boot/syslinux directory.
  ```mkboot``` will not affect existing partitions or
  existing data on a usb drive.
  Before copying, the (first) target partition can be mounted or unmounted.
  After copying, its mount status will remain the same.

In contrast to its predecessors mk-boot-usb, mbootu2,
and the unpopularised mbootu3,
```mbootuz.py``` does not try to everything for you in one step.
In particular, it does not copy any minimal linux
(e.g. ttylinux or finnix) to the target.
After years of experimenting with linux newbie students,
it is decided that the task of creating a bootable usb
be separated into two parts.
```mbootuz.py``` is intended to be the lower-level part of the task.
Thus the ease of use is sacrificed in exchange for cleaner,
simpler code and better maintainability.
The higher-level part of the task is to be completed
by a somewhat knowledgeable sys admin (the person reading this doc ^_^).
S/he will then create an extlinux.conf and write a short shell script
to invoke ```mbootuz.py``` and copy the chosen linux live cd
to the vfat partition or restore a pre-built linux image
to the linux partition, according to the real locations
of the necessary files.

```mbootuz.py``` is developed in a lubuntu 16.04 system
running python 2.7.12 . It requires the fdisk command
and the extlinux package.

## Usage Scenarios

I ask my students to bring to the computer lab
one empty usb drive of size >= 8GB,
and as many other usb drives as possible,
each having >= 512MB available spaces,
and promise not to disturb their existing files on the latter.

To each of the usb drives containing precious data
that cannot be destroyed, I run something like this:
```
    mount /dev/sdz1 /mnt/tmp1
    mbootuz.py mkboot /dev/sdz
    cp -a .../sysrcd .../clonezilla-live-2.5.0-25-amd64.iso /mnt/tmp1
    umount /dev/sdz1
```
The second command installs the boot loader, etc. into /dev/sdz1 .
Note: the sysrcd subdirectory in the cp command should contain
[all the necessary files](http://www.system-rescue-cd.org/manual/Installing_SystemRescueCd_on_the_disk/)
mentioned in extlinux.conf .

To the empty usb drive, I run something like this:
```
    mbootuz.py wipe -L 7G -t 83 /dev/sdz
    mbootuz.py mkboot /dev/sdz
    fsarchiver restfs .../lubuntu-16.04-a.fsa id=0,dest=/dev/sdz2
```
The first command wipes the usb drive, creates an
unformatted 7GB linux partition (type 0x83) /dev/sdz2,
and leaves all the remaining space to the
vfat partition /dev/sdz1, formatted.
The second command installs the boot loader, etc. into /dev/sdz1 .
The third command restores a full linux operating system to /dev/sdz2 .

Or, if you somehow (start from
[here](https://github.com/zfsonlinux/zfs/wiki/Ubuntu-16.10-Root-on-ZFS))
managed to manually install some linux in a usb drive
(let's call its zpool "stem-cell"), then you can use it to boot and 
clone a snapshot of this (running!) OS to a new drive flashy-new-usb as follows
(change paths acoording to your situation):
```
    mount /dev/sdz1 /mnt/tmp1
    cp -r /boot /mnt/tmp2/boot/lu1604z
    umount /dev/sdz1
    zpool create flashy-new-usb /dev/sdz2
    zpool import stem-cell
    zfs list -t snapshot
    zfs send -R stem-cell/ROOT/lu1604z@6-deploy | zfs receive -d -Fu flashy-new-usb
```
**Note**: You must ```zpool export flashy-new-usb ; umount /dev/sdz1```
before you can **remove** the new usb or before you can use **kvm** to test it!

## Options

- ```-L size``` Allocate _size_ space to the linux partition.
  For example, ```-L 6G``` , ```-L 6144M```, and ```-L 6291456K``` are the same.
- ```-x max_size``` Refuse to process target drive of size
  greater than *max_size*. The default is a relatively small
  value so that only usb flash drives gets processed,
  and external/internal harddisks are not
  inadvertently damaged. You can raise this value if you know
  what you are doing.
- ```-t type``` Set linux partition to type _type_ in fdisk.
  For ext2/3/4 file systems, use ```-t 83```.
  For zfs, use ```-t bf```.

## Limitations

To protect the user from inadvertent and disastrous mistakes,
```mbootuz.py``` refuses to work on anything other than /dev/sd[b-z] .
Obviously you can change the source code to remove this limitation.


## 簡介

```mbootuz.py``` 有兩個子指令：
- ```wipe``` 把隨身碟上的所有資料燒毀/清空/刪除、
  建立一個 vfat 分割及一個 linux 分割、
  格式化 vfat 分割並把它設成可開機。
- ```mkboot``` 把 mbr 安裝到隨身碟上、
  把 /usr/lib/syslinux 複製到 vfat 分割的 /boot 子目錄下，
  並且在 /boot/syslinux 這個新的子目錄下安裝 extlinux。
  ```mkboot``` 不會響到隨身碟上既有的分割或資料。
  在複製之前， 第一分割可以是已掛載或已卸載。
  複製結束之後， 它的掛載狀況會跟原來一樣。

```mbootuz.py``` 跟它的前身們 (mk-boot-usb、 mbootu2、
很少人知道的 mbootu3) 不一樣。
它沒有要幫你把所有工作一步做到位。
比方說， 它不會把任何精簡版 linux (例如 ttylinux 或 finnix)
複製到隨身碟上。 根據多年拿學生當白老鼠實驗的經驗，
最後決定： 製作開機隨身碟這件事， 應該分成兩部分。
```mbootuz.py``` 負責低階的部分。
所以犧牲便利性， 換取程式碼的乾淨、簡單、好維護。
高階的那部分， 應該由一位略具經驗的系統管理員 (這份文件的讀者 ^_^) 來完成。
他/她會建一個 extlinux.conf 設定檔， 並且寫一個簡短的 shell script，
裡面呼叫 ```mbootuz.py``` 並且根據現場環境的實際路徑把他所選擇的
linux live cd 複製到 vfat 分割， 或是把預先建立好的
linux 映像檔還原到 linux 分割。

```mbootuz.py``` 在 lubuntu 16.04 上面，
以 python 2.7.12 開發。 它需要用到 fdisk 指令跟 extlinux 套件。

## 使用情境

我請學生攜帶一顆至少 8GB 的空白隨身碟，
還有盡量多顆 「剩餘 >= 512MB 空間」 的其他任何隨身碟來上課，
也告訴他們後者的資料不會被摧毀。

對那些內含重要資料、 不可毀壞的隨身碟， 我這樣下指令：
```
    mount /dev/sdz1 /mnt/tmp1
    mbootuz.py mkboot /dev/sdz
    cp -a .../sysrcd .../clonezilla-live-2.5.0-25-amd64.iso /mnt/tmp1
    umount /dev/sdz1
```
其中第二個指令把開機管理員等等安裝到 /dev/sdz1。
又， cp 指令裡的 sysrcd 子目錄應包含 extlinux.conf 裡面提及的所有檔案。

對那顆空白隨身碟， 我這樣下指令：
```
    mbootuz.py wipe -L 7G -t 83 /dev/sdz
    mbootuz.py mkboot /dev/sdz
    fsarchiver restfs .../lubuntu-16.04-a.fsa id=0,dest=/dev/sdz2
```
第一個指令把隨身碟清空、 建立一個未格式化的 7GB
linux 分割 (type 0x83) /dev/sdz2、
把剩下所有空間留給 vfat 分割 /dev/sdz1， 並且格式化。
第二個指令把開機管理員等等安裝到 /dev/sdz1。
第三個指令把一個完整的 linux 作業系統還原到 /dev/sdz2。

或者， 如果你已成功地 [把 linux 栽種到一顆隨身碟的 zfs 裡](https://newtoypia.blogspot.tw/2017/03/zfs-root.html)
(姑且稱它的 zpool 為 "stem-cell" 好了) 那麼你就可以用它開機，
並且把這個 (正在運行的!) 作業系統的某個快照複製給一顆新的開機碟 flashy-new-usb
(請自行把指令中的路徑改成你真實的狀況)：
```
    mount /dev/sdz1 /mnt/tmp1
    cp -r /boot /mnt/tmp2/boot/lu1604z
    umount /dev/sdz1
    zpool create flashy-new-usb /dev/sdz2
    zpool import stem-cell
    zfs list -t snapshot
    zfs send -R stem-cell/ROOT/lu1604z@6-deploy | zfs receive -d -Fu flashy-new-usb
```
**注意**： 請務必先 ```zpool export flashy-new-usb ; umount /dev/sdz1```
然後才可以**拔出**這顆新的隨身碟， 或用 **kvm** 去測試它。

## 選項

- ```-L size``` 配置 _size_ 空間給 linux 分割。
  比方說， ```-L 6G``` 、 ```-L 6144M``` 、 ```-L 6291456K``` 效果相同。
- ```-x max_size``` 拒絕處理容量超過 *max_size* 的隨身碟/硬碟。
  預設的數值只能處理隨身碟， 目的是要排除內接/外接硬碟，
  避免造成意外災害。 如果你知道自己在幹嘛， 可以把這個數值改大一些。
- ```-t type``` 在 fdisk 裡面， 把 linux 分割的 type 設成 _type_。
  例如 ext2/3/4 檔案系統，請用 ```-t 83``` ；
  zfs 檔案系統，請用 ```-t bf```。

## 限制

為避免使用者意外造成嚴重損害， ```mbootuz.py```
只處理 /dev/sd[b-z] 這些裝置。
當然， 你也可以自己修改原始碼， 移除這個限制。

