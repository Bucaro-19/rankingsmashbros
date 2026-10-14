const test=require('node:test'),assert=require('node:assert/strict'),f=require('../../ranking-smash-ultimate/frame-tools.js');
test('inclusive frame window, no invented timing, no shield drop added twice',()=>{
 const options=[{name:'Uno',frame:3},{name:'Dos',frame:6},{name:'Tres',frame:7}];
 assert.deepEqual(f.fits(options,-6),options.slice(0,2));assert.deepEqual(f.fits(options,-2),[]);assert.deepEqual(f.fits(options,null),[]);assert.deepEqual(f.fits(options,6),[]);
});
test('actual sheets, omitted character, no main, short options and escaped names',()=>{
 const facts={fastest:{name:'<script>',frame:2,damage:2.2},oos:[{name:'Neutral',frame:6}]};
 const html=f.sheet({title:'Yo',main:'link',mainName:'Link',facts,moves:[{name:'Golpe',onShield:-6},{name:'Más seguro',onShield:-5}]});
 assert.match(html,/✓ Te entran: Neutral \(frame 6\)/);assert.match(html,/Ninguna de tus opciones/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
 assert.match(f.sheet({title:'Sin ficha',facts:null}),/Aún no hay ficha técnica/);
 assert.match(f.sheet({title:'Yo',main:null,mainName:'main',facts,moves:null}),/Sin main detectado/);
 assert.match(f.sheet({title:'Yo',main:'link',mainName:'Link',facts,moves:null}),/No tenemos golpes/);
});
test('credit only when provided by server; no guessed game version',()=>{
 assert.equal(f.credit(null),'');assert.match(f.credit({gameVersion:null}),/versión no declarada por la fuente/);assert.match(f.credit({gameVersion:'13.0.1'}),/versión 13.0.1 del juego/);
});
