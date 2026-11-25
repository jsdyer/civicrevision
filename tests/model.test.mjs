import test from 'node:test';import assert from 'node:assert/strict';import {filterRecords,safeHttps,ageHours,readableDelta,validSnapshot} from '../web/model.mjs';
const rows=[{title:'New article beyond defaults',comment:'Added a source',topics:['custom'],citations_added:[{text:'Official report'}],citations_removed:[],reversion:null},{title:'Parliament',comment:'Restore',topics:['institutions'],citations_added:[],citations_removed:[],reversion:'Wikipedia tagged undo'}];
test('filters dynamic topics and citation bodies',()=>{assert.equal(filterRecords(rows,{topic:'custom',query:'official',kind:'citations'}).length,1);});
test('reversion filtering does not confuse ordinary edits',()=>assert.equal(filterRecords(rows,{kind:'reversions'})[0].title,'Parliament'));
test('no match stays empty',()=>assert.equal(filterRecords(rows,{query:'not here'}).length,0));
test('only credential-free HTTPS citation links',()=>{assert.equal(safeHttps('javascript:alert(1)'),null);assert.equal(safeHttps('https://x:y@example.com'),null);assert.equal(safeHttps('https://example.com/path'),'https://example.com/path');});
test('age uses source checked time and handles invalid values',()=>{assert.equal(ageHours('2026-11-25T00:00:00Z',Date.parse('2026-11-25T12:00:00Z')),12);assert.equal(ageHours('bad'),Infinity);});
test('nullable size delta remains unknown',()=>{assert.equal(readableDelta(null),'Size comparison unavailable');assert.equal(readableDelta(5),'+5 bytes');});
test('validates capture basics',()=>{assert(!validSnapshot({}));assert(validSnapshot({schema:'civicrevision.v1',records:[],topics:[],history:[],checked_at:'2026-11-25T00:00:00Z'}));});
