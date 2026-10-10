import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../frontend/src/locales');
const ru=JSON.parse(fs.readFileSync(path.join(root,'ru.json')));const en=JSON.parse(fs.readFileSync(path.join(root,'en.json')));
if(JSON.stringify(Object.keys(ru).sort())!==JSON.stringify(Object.keys(en).sort()))throw Error('Translation keys differ');
for(const key of Object.keys(ru)){const placeholders=value=>JSON.stringify((value.match(/\{\{\w+\}\}/g)||[]).sort());if(placeholders(ru[key])!==placeholders(en[key]))throw Error(`Placeholder mismatch: ${key}`);if(!ru[key]||!en[key])throw Error(`Empty translation: ${key}`)}
console.log(`Translation parity verified: ${Object.keys(ru).length} keys`);
