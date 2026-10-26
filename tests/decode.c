/* Test-only decoder, never linked into the driver. */
#include "jbig.h"
#include <stdio.h>
#include <stdlib.h>
int main(void)
{
    struct jbg_dec_state state;
    jbg_dec_init(&state);
    jbg_dec_maxsize(&state, 5376, 8500);
    unsigned char block[65536];
    size_t n, used;
    int result=JBG_EAGAIN;
    while((n=fread(block,1,sizeof block,stdin))) {
        result=jbg_dec_in(&state,block,n,&used);
        if((result!=JBG_EOK && result!=JBG_EAGAIN) || used!=n) return 1;
    }
    if(result!=JBG_EOK) return 2;
    printf("%lu %lu\n",jbg_dec_getwidth(&state),jbg_dec_getheight(&state));
    n=jbg_dec_getsize(&state);
    if(fwrite(jbg_dec_getimage(&state,0),1,n,stdout)!=n) return 3;
    jbg_dec_free(&state);
    return 0;
}
