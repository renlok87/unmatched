const fs=require('fs');const f=process.argv[2];const t=fs.readFileSync(f,'utf8');
const found=(t.match(/Found (\d+) automation tests/)||[])[1];
const done=[...t.matchAll(/Test Completed\. Result=\{(\w+)\} Name=\{(.*?)\} Path=\{(.*?)\}/g)];
const by={};for(const m of done){by[m[1]]=(by[m[1]]||0)+1;}
const bad=done.filter(m=>m[1]!=='Success').map(m=>m[1]+': '+m[3]);
const exit=(t.match(/TEST COMPLETE\. EXIT CODE: (-?\d+)/)||[])[1];
const errs=(t.match(/^.*(Error:|Fatal).*$/gm)||[]).filter(l=>/Automation|Fatal/.test(l)).slice(0,10);
const ring=done.filter(m=>/TeamRing/.test(m[3])).map(m=>m[1]+': '+m[3]);
console.log(JSON.stringify({log:f,found:+found,completed:done.length,byResult:by,exitCode:exit==null?null:+exit,notSuccess:bad,teamRing:ring,automationErrorLines:errs},null,1));
