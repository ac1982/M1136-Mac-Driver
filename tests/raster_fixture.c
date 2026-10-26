/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv)
{
    const char *mode=argc>1?argv[1]:"valid";
    unsigned sync=CUPS_RASTER_SYNC;
    if(fwrite(&sync,sizeof sync,1,stdout)!=1) return 1;
    cups_page_header2_t h={0};
    h.HWResolution[0]=h.HWResolution[1]=600;
    h.PageSize[0]=595; h.PageSize[1]=842;
    h.cupsWidth=129; h.cupsHeight=32;
    h.cupsBitsPerColor=h.cupsBitsPerPixel=8;
    h.cupsBytesPerLine=129; h.cupsNumColors=1;
    h.cupsColorSpace=CUPS_CSPACE_W;
    h.NumCopies=1;
    if(!strcmp(mode,"uncollated")) h.NumCopies=3;
    if(!strcmp(mode,"copies99")) h.NumCopies=99;
    if(!strcmp(mode,"copies0")) h.NumCopies=0;
    if(!strcmp(mode,"copies100")) h.NumCopies=100;
    if(!strcmp(mode,"copiesoverflow")) h.NumCopies=0xffffffffu;
    if(!strcmp(mode,"a4")) {h.cupsWidth=4758;h.cupsHeight=6817;h.cupsBytesPerLine=4758;}
    if(!strcmp(mode,"letter")) {h.PageSize[0]=612;h.PageSize[1]=792;h.cupsWidth=4900;h.cupsHeight=6400;h.cupsBytesPerLine=4900;}
    if(!strcmp(mode,"max")) {h.cupsWidth=5200;h.cupsHeight=8500;h.cupsBytesPerLine=5200;}
    if(!strcmp(mode,"width")) h.cupsWidth=5201;
    if(!strcmp(mode,"height")) h.cupsHeight=8501;
    if(!strcmp(mode,"stride")) h.cupsBytesPerLine=128;
    if(!strcmp(mode,"color")) h.cupsColorSpace=CUPS_CSPACE_RGB;
    if(!strcmp(mode,"duplex")) h.Duplex=1;
    if(!strcmp(mode,"tumble")) h.Tumble=1;
    if(!strcmp(mode,"dpi")) h.HWResolution[0]=1200;
    if(!strcmp(mode,"paper")) h.PageSize[0]=1;
    if(!strcmp(mode,"bits")) h.cupsBitsPerColor=1;
    unsigned pages=(!strcmp(mode,"multi") || !strcmp(mode,"collated") || !strcmp(mode,"mixedcopies"))?3:!strcmp(mode,"limit")?500:!strcmp(mode,"overlimit")?501:1;
    unsigned char row[8192];
    for(unsigned p=0;p<pages;++p) {
        if(!strcmp(mode,"mixedcopies")) h.NumCopies=p+1;
        if(fwrite(&h,sizeof h,1,stdout)!=1) return 2;
        if(!strcmp(mode,"truncated")) break;
        for(unsigned y=0;y<h.cupsHeight;++y) {
            for(unsigned x=0;x<sizeof row;++x) row[x]=(unsigned char)((x+y+p)%256);
            if(fwrite(row,1,h.cupsBytesPerLine,stdout)!=h.cupsBytesPerLine) return 3;
        }
    }
    return fflush(stdout) ? 1 : 0;
}
