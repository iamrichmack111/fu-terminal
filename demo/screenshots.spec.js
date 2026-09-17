const { test } = require('@playwright/test'); const path=require('path');
for (const name of ['index','safety','architecture']) test(name, async ({page})=>{await page.goto('file://'+path.join(__dirname,name+'.html')); await page.screenshot({path:path.join(__dirname,'..','media',name==='index'?'investigate-disk.png':name+'.png'),fullPage:true});});
