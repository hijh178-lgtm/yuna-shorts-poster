"""Publish only the approved five-day carousel queue. Durable checkpoints prevent duplicate retries."""
import base64, datetime as dt, hashlib, json, os, pathlib, time, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
QUEUE='carousel-20261106/queue.json'
STATE='carousel-20261106/state.json'
G='https://graph.instagram.com/v26.0/'

def request(url, token=None, data=None, method=None, form=False):
    headers={'User-Agent':'yuna-carousel-scheduler'}
    if token: headers['Authorization']='Bearer '+token
    if data is not None:
        headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
        data=urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
    except Exception as e:
        # Never emit request headers, credentials or raw server bodies.
        raise RuntimeError('Remote request failed: '+type(e).__name__+' '+str(getattr(e,'code',''))) from None

def eligible(row, now):
    due=dt.datetime.fromisoformat(row['at'])
    return due<=now<due+dt.timedelta(hours=24)

def validate(rows):
    if len(rows)!=5 or len({r['id'] for r in rows})!=5:raise RuntimeError('Unexpected queue')
    for r in rows:
        if r['username']!='yuna._log' or len(r['images'])!=5:raise RuntimeError('Wrong account/image count')
        if len(r['caption'])>2200 or not r['caption'].startswith('[광고]') or r['affiliate_url'] not in r['caption']:raise RuntimeError('Caption invalid')
        for im in r['images']:
            content=(ROOT/im['file']).read_bytes()
            if not content.startswith(b'\xff\xd8') or hashlib.sha256(content).hexdigest()!=im['sha256']:raise RuntimeError('Asset mismatch')

def main():
    rows=json.loads((ROOT/QUEUE).read_text(encoding='utf-8'));validate(rows)
    token=os.environ['IG_TOKEN'];gh=os.environ['GH_TOKEN'];repo=os.environ['GITHUB_REPOSITORY']
    def ig(path,data=None):return request(G+path,token,data,form=True)
    me=ig('me?fields=user_id,username')
    if me.get('username')!='yuna._log':raise RuntimeError('Unexpected Instagram identity')
    uid=me.get('user_id') or me['id']
    state_url=f'https://api.github.com/repos/{repo}/contents/{STATE}'
    remote=request(state_url,gh);state=json.loads(base64.b64decode(remote['content']));sha=remote['sha']
    def save():
        nonlocal sha
        body={'message':'carousel: checkpoint','sha':sha,'content':base64.b64encode(json.dumps(state,ensure_ascii=False,indent=2).encode()).decode()}
        result=request(state_url,gh,body,method='PUT');sha=result['content']['sha']
    now=dt.datetime.now(dt.timezone.utc)
    print('Validated account yuna._log; 5 carousels; 25 JPEG assets; captions and hashes OK')
    if os.environ.get('DRY_RUN','').lower()=='true':
        for r in rows:
            for im in r['images']:
                url=f'https://raw.githubusercontent.com/{repo}/main/'+urllib.parse.quote(im['file'])
                with urllib.request.urlopen(url,timeout=30) as response:blob=response.read()
                if hashlib.sha256(blob).hexdigest()!=im['sha256']:raise RuntimeError('Public asset mismatch')
        print('Preflight passed: 25 public assets accessible; no publication performed');return
    for row in rows:
        if not eligible(row,now):continue
        st=state.setdefault(row['id'],{})
        if st.get('phase') in ['published','failed','needs_review']:continue
        if st.get('phase')=='publishing':
            # An interrupted publish is reconciled by exact caption; never blindly republished.
            recent=ig(f'{uid}/media?fields=id,caption,permalink&limit=50').get('data',[])
            hits=[m for m in recent if m.get('caption','').strip()==row['caption'].strip()]
            if len(hits)==1:st.update(phase='published',media_id=hits[0]['id'],permalink=hits[0].get('permalink'));save()
            else:st.update(phase='needs_review',reason='Previous publish outcome needs confirmation');save();raise RuntimeError('Ambiguous publish held for review')
            continue
        try:
            st.setdefault('children',[]);st['phase']='creating';save()
            for im in row['images'][len(st['children']):]:
                url=f'https://raw.githubusercontent.com/{repo}/main/'+urllib.parse.quote(im['file'])
                child=ig(f'{uid}/media',{'image_url':url,'is_carousel_item':'true'})
                st['children'].append(child['id']);save()
            if not st.get('container'):
                box=ig(f'{uid}/media',{'media_type':'CAROUSEL','children':','.join(st['children']),'caption':row['caption']})
                st['container']=box['id'];save()
            for _ in range(40):
                status=ig(st['container']+'?fields=status_code')['status_code']
                if status=='FINISHED':break
                if status in ['ERROR','EXPIRED']:raise RuntimeError('Container rejected')
                time.sleep(3)
            else:raise RuntimeError('Container processing timeout')
            st.update(phase='publishing',publish_started=dt.datetime.now(dt.timezone.utc).isoformat());save()
            result=ig(f'{uid}/media_publish',{'creation_id':st['container']})
            st.update(phase='published',media_id=result['id'],published_at=dt.datetime.now(dt.timezone.utc).isoformat());save()
            info=ig(result['id']+'?fields=permalink,caption,children{id}')
            st.update(permalink=info.get('permalink'),verified=info.get('caption','').strip()==row['caption'].strip() and len(info.get('children',{}).get('data',[]))==5);save()
            print('Published',row['id'],st.get('permalink'))
        except Exception as e:
            if st.get('phase') not in ['publishing','published']:st.update(phase='failed',reason=str(e));save()
            raise

if __name__=='__main__':main()
