#!/usr/bin/env python3
"""Capture public Wikipedia revisions. Failed collections do not replace good data."""
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib, html, json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path
from urllib.parse import urlencode, quote, urlsplit
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
UA='CoolCodeCivicRevision/1.0 (+https://coolcode.ca/civicrevision/; public revision observatory)'

def validate_config(config):
    if not re.fullmatch(r'[a-z]{2,12}(?:-[a-z]{2,12})?',config.get('language','')): raise ValueError('Invalid Wikipedia language')
    count=config.get('revisions_per_article')
    if not isinstance(count,int) or not 2<=count<=50: raise ValueError('Choose 2–50 revisions per article')
    if not isinstance(config.get('topics'),list) or not config['topics']:raise ValueError('At least one topic required')
    ids=set(); titles=set()
    for topic in config['topics']:
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',topic['id']) or topic['id'] in ids:raise ValueError('Unique topic ID required')
        ids.add(topic['id'])
        if not topic.get('label') or not topic.get('articles'):raise ValueError('Topic needs label and articles')
        for title in topic['articles']:
            if not isinstance(title,str) or not title.strip() or len(title)>250 or '|' in title:raise ValueError('Invalid article title')
            titles.add(title)
    if len(titles)>100:raise ValueError('At most 100 configured articles per collector')
    return sorted(titles)

def request(url,limit):
    # curl has the same bounded timeout on CI and on operator machines.
    proc=subprocess.run(['curl','--fail-with-body','--silent','--show-error','--location','--max-time','45','--max-filesize',str(limit),'-A',UA,url],capture_output=True,timeout=50)
    if proc.returncode:raise RuntimeError('Wikimedia request failed; existing capture preserved')
    if len(proc.stdout)>limit:raise ValueError('Wikimedia response exceeded configured limit')
    data=json.loads(proc.stdout)
    if 'error' in data:raise ValueError('Wikimedia API returned an error')
    return data

def citations(text):
    found={}
    for match in re.finditer(r'<ref\b[^>]*>([\s\S]*?)</ref\s*>',text,re.I):
        body=re.sub(r'\s+',' ',match.group(1)).strip()
        if not body:continue
        key=hashlib.sha256(body.encode()).hexdigest()[:20]
        urls=re.findall(r'https?://[^\s<>|}\]"\']+',body)
        found[key]={'id':key,'text':body[:2000],'urls':list(dict.fromkeys(urls))[:5]}
    return found

def readable(text):
    s=re.sub(r'<ref\b[^>]*>[\s\S]*?</ref\s*>',' [citation] ',text,flags=re.I)
    s=re.sub(r'<ref\b[^>]*/\s*>',' [citation] ',s,flags=re.I)
    s=re.sub(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]',r'\1',s)
    s=re.sub(r"'{2,5}",'',s)
    s=re.sub(r'<!--.*?-->','',s,flags=re.S)
    return html.unescape(s).strip()

def compare(old,new):
    before=old.splitlines();after=new.splitlines();changes=[]
    for kind,a,b,c,d in SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
        if kind=='equal':continue
        removed=readable('\n'.join(before[a:b]));added=readable('\n'.join(after[c:d]))
        changes.append({'kind':kind,'before':removed[:3500],'after':added[:3500],'truncated':len(removed)>3500 or len(added)>3500})
    a=citations(old);b=citations(new)
    return {'changes':changes[:30],'changes_truncated':len(changes)>30,'citations_added':[b[k]for k in b.keys()-a.keys()],'citations_removed':[a[k]for k in a.keys()-b.keys()]}

def revision_records(page,topic,language,checked):
    revisions=page.get('revisions',[]);records=[]
    by_id={r['revid']:r for r in revisions}
    for i,r in enumerate(revisions[:-1]):
        old=by_id.get(r.get('parentid'));slot=r.get('slots',{}).get('main',{});oldslot=(old or {}).get('slots',{}).get('main',{})
        record={'id':f"{language}:{r['revid']}",'revision_id':r['revid'],'parent_id':r.get('parentid'),'title':page['title'],'language':language,'topics':topic,'timestamp':r['timestamp'],'first_observed_at':checked,'comment':r.get('comment','[edit summary unavailable]'),'tags':r.get('tags',[]),'source_url':f'https://{language}.wikipedia.org/w/index.php?title={quote(page["title"])}&diff={r["revid"]}&oldid={r.get("parentid",0)}','revision_url':f'https://{language}.wikipedia.org/w/index.php?oldid={r["revid"]}','bytes_delta':r.get('size',0)-(old or {}).get('size',0) if old else None,'comparison_available':False,'changes':[],'citations_added':[],'citations_removed':[],'changes_truncated':False}
        if old and 'content' in slot and 'content' in oldslot:
            record.update(compare(oldslot['content'],slot['content']),comparison_available=True)
        else:record['comparison_note']='A parent revision or readable content was unavailable; use the original revision link.'
        tags=set(record['tags']);record['reversion']='Wikipedia tagged undo/rollback/revert' if tags&{'mw-rollback','mw-undo','mw-manual-revert'} else None
        if not record['reversion'] and r.get('sha1') and any(x.get('sha1')==r['sha1'] for x in revisions[i+2:]):record['reversion']='Matches earlier content in this captured revision window'
        records.append(record)
    return records

def merge_records(existing,incoming):
    result={r['id']:r for r in existing}
    for r in incoming:
        if r['id'] not in result:result[r['id']]=r
    return sorted(result.values(),key=lambda r:(r['timestamp'],r['id']),reverse=True)

def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')

def rss(records,label,url,checked):
    root=ET.Element('rss',version='2.0');channel=ET.SubElement(root,'channel')
    for name,value in [('title','Civic Revision · '+label),('link',url),('description','Captured Wikipedia revisions, not an endorsement or a finding of institutional misconduct.'),('lastBuildDate',datetime.fromisoformat(checked.replace('Z','+00:00')).strftime('%a, %d %b %Y %H:%M:%S GMT'))]:ET.SubElement(channel,name).text=value
    for r in records[:50]:
        item=ET.SubElement(channel,'item');ET.SubElement(item,'title').text=r['title']+': '+r['comment'];ET.SubElement(item,'link').text=r['source_url'];ET.SubElement(item,'guid',isPermaLink='false').text=r['id'];ET.SubElement(item,'pubDate').text=datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')).strftime('%a, %d %b %Y %H:%M:%S GMT');ET.SubElement(item,'description').text=f"{r['comment']} — citations added {len(r['citations_added'])}, removed {len(r['citations_removed'])}. {r.get('reversion') or 'No reversion signal identified.'} Wikipedia contributors; CC BY-SA."
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def collect(root=ROOT):
    config=json.loads((root/'sources.json').read_text());titles=validate_config(config);checked=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');language=config['language'];data_dir=root/'web/data';existing=[]
    for p in sorted((data_dir/'history').glob('*.json')):
        archive=json.loads(p.read_text())
        if archive.get('schema')!='civicrevision.history.v1' or not isinstance(archive.get('records'),list):raise ValueError('Invalid existing history; refusing to replace it')
        existing.extend(archive['records'])
    incoming=[];coverage=[];old_ids={r['revision_id']for r in existing}
    for title in titles:
        params={'action':'query','format':'json','formatversion':2,'prop':'revisions','titles':title,'redirects':1,'rvprop':'ids|timestamp|comment|tags|size|sha1|content','rvslots':'main','rvlimit':config['revisions_per_article'],'maxlag':5}
        response=request(f'https://{language}.wikipedia.org/w/api.php?'+urlencode(params),config['max_response_bytes']);pages=response.get('query',{}).get('pages',[])
        if len(pages)!=1 or pages[0].get('missing') or not pages[0].get('revisions'):raise ValueError(f'Article unavailable: {title}')
        page=pages[0];topics=[t['id']for t in config['topics'] if title in t['articles']];revs=page['revisions'];prior=[r for r in existing if r['language']==language and r['title']==page['title']]
        gap=bool(prior and not any(r['revid'] in old_ids for r in revs))
        coverage.append({'requested_title':title,'title':page['title'],'topics':topics,'revisions_returned':len(revs),'oldest_returned_at':revs[-1]['timestamp'],'latest_revision_at':revs[0]['timestamp'],'window_gap':gap})
        incoming.extend(revision_records(page,topics,language,checked));time.sleep(.15)
    records=merge_records(existing,incoming);months={}
    for r in records:months.setdefault(r['timestamp'][:7],[]).append(r)
    # All source work succeeds before staging. A failure leaves the previous tree untouched.
    with tempfile.TemporaryDirectory(dir=root,prefix='.capture-') as temporary:
        stage=Path(temporary)/'data';stage.mkdir();entries=[]
        for month,items in sorted(months.items(),reverse=True):
            relative=f'history/{month}.json';path=stage/relative;write_json(path,{'schema':'civicrevision.history.v1','month':month,'records':items});raw=path.read_bytes();entries.append({'month':month,'path':relative,'count':len(items),'sha256':hashlib.sha256(raw).hexdigest()})
        snapshot={'schema':'civicrevision.v1','checked_at':checked,'language':language,'topics':config['topics'],'coverage':coverage,'records':records[:200],'total_retained':len(records),'history':entries,'revision_window':config['revisions_per_article']}
        write_json(stage/'snapshot.json',snapshot);write_json(stage/'status.json',{'checked_at':checked,'articles':len(titles),'records':len(records),'latest_revision_at':records[0]['timestamp'] if records else None,'coverage_gaps':sum(x['window_gap']for x in coverage)})
        feeds=stage/'feeds';feeds.mkdir();(feeds/'all.xml').write_bytes(rss(records,'All topics','https://coolcode.ca/civicrevision/',checked))
        for topic in config['topics']:(feeds/(topic['id']+'.xml')).write_bytes(rss([r for r in records if topic['id']in r['topics']],topic['label'],'https://coolcode.ca/civicrevision/?topic='+topic['id'],checked))
        backup=Path(temporary)/'previous'
        if data_dir.exists():os.replace(data_dir,backup)
        try:os.replace(stage,data_dir)
        except BaseException:
            if backup.exists():os.replace(backup,data_dir)
            raise
    print(json.dumps({'checked_at':checked,'articles':len(titles),'retained_revisions':len(records),'new_revisions':len(records)-len(existing)}))

if __name__=='__main__':collect()
