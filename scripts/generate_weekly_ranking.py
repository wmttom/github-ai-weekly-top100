#!/usr/bin/env python3
"""Weekly GitHub AI Top100 generator. Fails closed when Trendshift is unavailable."""
from __future__ import annotations
import argparse, csv, json, math, os, re, sys, time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TZ = ZoneInfo("Asia/Shanghai")
COLS = ["排名","项目","热度分","对比上周排名变动","项目分类","项目 License","项目简介"]
URLS = {"monthly":"https://trendshift.io/monthly","weekly":"https://trendshift.io/weekly","daily":"https://trendshift.io/"}
MINS = {"monthly":20,"weekly":20,"daily":5}
WEIGHTS = {"monthly":42000,"weekly":72000,"daily":30000}
ALIASES = {"chopratejas/headroom":"headroomlabs-ai/headroom","alishahry1/free-claude-code":"Alishahryar1/free-claude-code"}
AI = (" ai ","llm","agent","agentic","mcp","rag","claude","codex","copilot","gpt","gemini","qwen","deepseek","machine learning","neural","inference","embedding","vector","ocr","tts","speech","voice","robot","world model","prompt")
BLOCK = ("curated list","programming examples","course curriculum","tutorial series","system prompt leaks","prompt leaks","iptv","proxy","vpn","debloat")
RULES = [
("Agent 搜索 / 趋势研究",("last30days","researches any topic","reddit","hacker news","web research","trend research","osint")),
("AI 视频生成 / 多媒体工作流",("video","storyboard","subtitle","dubbing","keyframes")),
("语音 / TTS / STT",("tts","text to speech","speech","voice","audio agent","transcrib","whisper")),
("AI 求职 / 招聘与职业运营",("job search","resume","career","hiring","recruit")),
("量化 / 金融 AI 代理",("trading","stock","finance","financial","portfolio","investment","quant","market data")),
("医疗 / 健康 AI",("medical","healthcare","clinical","biomedical")),
("机器人 / 3D / 具身智能",("robot","embodied","world model","cad","3d","urdf","autonomous driving")),
("Agent 记忆 / 长上下文记忆",("memory","context engine","long-term","knowledge graph","context compression","token compression","harness performance optimization")),
("浏览器自动化 / Web Agent",("browser","web agent","headless browser","puppeteer","playwright","gui agent")),
("AI 安全 / Agent 安全治理",("security","cybersecurity","pentest","vulnerability","red team","threat","sandbox","destructive command","malicious")),
("AI 编码助手 / Agent Skills",("coding agent","code review","claude code","codex","developer tool","ide","codebase","agent skill","skills","software development","design language")),
("MCP Server / MCP 工具链",("mcp","model context protocol")),
("RAG / 知识库 / 文档解析",("rag","retrieval","vector","embedding","knowledge base","document","pdf","markdown","ocr","semantic search")),
("LLM 网关 / 路由与代理层",("gateway","model router","routing","multi-provider")),
("AI 可观测 / LLM 评测",("observability","evaluation","tracing","benchmark","monitoring")),
("本地 LLM / 高效推理",("local llm","inference","quantization","low-bit","1-bit","gguf","cuda","vulkan")),
("AI Agent / 工作流编排",("agent","agentic","multi-agent","workflow","orchestration","automation")),]
CAT = {
"Agent 搜索 / 趋势研究":("面向 agent 的外部信息检索与趋势研究","近期信息分散在多个平台且人工验证成本高","市场调研、竞品监测、热点验证和周期性研究报告"),
"AI 视频生成 / 多媒体工作流":("面向视频生成、理解与自动化制作","从脚本、素材到成片的链路长且后期成本高","短视频、营销素材、演示视频和多媒体内容生产"),
"语音 / TTS / STT":("面向语音生成、识别与音频交互","配音、转写和实时语音应用搭建成本高","播客、会议转写、数字人配音和语音助手"),
"AI 求职 / 招聘与职业运营":("面向求职与招聘流程自动化","岗位筛选、材料定制和候选人评估重复耗时","岗位匹配、简历优化、招聘初筛和申请跟踪"),
"量化 / 金融 AI 代理":("面向金融研究、市场分析与投研自动化","行情、新闻和指标分散且人工整理成本高","个股研究、市场复盘、策略实验和投资分析"),
"医疗 / 健康 AI":("面向医学文本与健康知识处理","医疗资料理解、检索和结构化分析成本高","医学知识检索、健康助手和临床文本分析"),
"机器人 / 3D / 具身智能":("面向机器人、三维内容与物理 AI","感知、建模、仿真和动作控制工具链分散","机器人训练、三维建模和具身智能研究"),
"Agent 记忆 / 长上下文记忆":("面向 agent 长期记忆与上下文治理","跨会话任务容易遗忘且长上下文成本持续增长","长期助理、代码库记忆和项目协作"),
"浏览器自动化 / Web Agent":("面向浏览器与网页任务自动化","模型理解网页后仍难稳定点击、填表和导航","网页研究、表单处理、自动测试和运营自动化"),
"AI 安全 / Agent 安全治理":("面向 AI 安全与自动化防护","agent 执行、代码与技能引入中的风险难及时识别","安全审计、漏洞分析、权限控制和运行治理"),
"AI 编码助手 / Agent Skills":("面向 coding agent 与工程协作","仓库理解、代码修改、验证和团队方法难稳定复用","代码生成、重构、调试、审查和研发提效"),
"MCP Server / MCP 工具链":("面向 MCP 工具接入与 agent 能力扩展","模型连接外部工具、数据源和业务系统缺少统一接口","企业工具层、浏览器代理和自动化系统"),
"RAG / 知识库 / 文档解析":("面向 RAG、知识检索与文档结构化","网页、PDF、代码和企业资料难被模型可靠利用","企业知识库、文档问答和研究检索"),
"LLM 网关 / 路由与代理层":("面向多模型统一接入与路由治理","不同模型接口、额度、成本和故障回退难统一管理","企业模型网关、多模型切换和成本控制"),
"AI 可观测 / LLM 评测":("面向 LLM 与 agent 的运行观测和质量评测","调用链、成本和输出质量难持续追踪","生产监控、RAG 评测和质量门禁"),
"本地 LLM / 高效推理":("面向本地模型运行与高效推理","云端依赖、隐私顾虑和低资源部署门槛高","离线助手、边缘设备和私有化部署"),
"AI Agent / 工作流编排":("面向多步骤 agent 与业务流程编排","规划、工具调用、状态管理和结果交付难串联","自动研究、业务自动化和多 agent 协作"),
"AI 基础设施 / 运行与平台层":("面向 AI 应用运行、工具链和平台基础设施","模型、工具、数据和运行环境接入分散","AI 平台、应用底座和生产化部署")}

@dataclass
class Rec:
    period:str; rank:int; repo:str; stars:int=0; forks:int=0; featured:int=0; desc:str=""; topics:list[str]=field(default_factory=list); new:bool=False; created:str|None=None; modified:str|None=None
@dataclass
class Cand:
    repo:str; trend:dict[str,Rec]=field(default_factory=dict); meta:dict=field(default_factory=dict); prev:dict|None=None; tier:int=0; raw:float=0; category:str=""; license:str="未知 / 未声明"; intro:str=""

def norm(s):
    s=" ".join((s or "").strip().split()); return ALIASES.get(s.lower(),s)
def key(s): return norm(s).lower()
def clean(s,n=500):
    s=re.sub(r"\s+"," ",(s or "")).strip(); return s if len(s)<=n else s[:n-1].rstrip(" ,.;，。；")+"…"
def iso(s):
    if not s:return None
    try:
        d=datetime.fromisoformat(s.replace("Z","+00:00")); return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:return None
def num(s):
    s=(s or "").lower().replace(",","").strip(); m=1
    if s.endswith("k"):m,s=1000,s[:-1]
    elif s.endswith("m"):m,s=1000000,s[:-1]
    try:return int(float(s)*m)
    except:return 0
def session(token=None):
    x=requests.Session(); r=Retry(total=5,backoff_factor=2,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset({"GET"}),respect_retry_after_header=True); x.mount("https://",HTTPAdapter(max_retries=r))
    x.headers.update({"User-Agent":"Mozilla/5.0 Chrome/136 Safari/537.36","Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8","Accept-Language":"en-US,en;q=0.9","Cache-Control":"no-cache"})
    if token:x.headers.update({"Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28"})
    return x

def fetch(run):
    run.mkdir(parents=True,exist_ok=True); s=session(); out={}
    for p,u in URLS.items():
        print("Fetching",p,u,flush=True); r=s.get(u,timeout=(30,180)); r.raise_for_status()
        if len(r.content)<40000:raise RuntimeError(f"Trendshift {p} response too small: {len(r.content)}")
        out[p]=run/f"{p}.html"; out[p].write_bytes(r.content)
    return out

def parse(path,period):
    html=path.read_text(encoding="utf-8",errors="replace"); soup=BeautifulSoup(html,"html.parser"); ld={}
    for sc in soup.find_all("script",{"type":"application/ld+json"}):
        try:d=json.loads(sc.string or sc.get_text())
        except:continue
        if isinstance(d,dict):
            for e in d.get("itemListElement",[]):
                it=e.get("item",{}) if isinstance(e,dict) else {}; name=it.get("name")
                if name:ld[key(name)]={"created":it.get("dateCreated"),"modified":it.get("dateModified")}
    rows=[]; seen=set()
    for div in soup.find_all("div"):
        if not {"hover:bg-accent","group","relative","flex","flex-col"}.issubset(set(div.get("class",[]))):continue
        a=next((a for a in div.find_all("a",href=True) if a["href"].startswith("/repositories/") and "/" in clean(a.get_text(" ",strip=True)) and not clean(a.get_text(" ",strip=True)).startswith("#")),None)
        if not a:continue
        repo=norm(clean(a.get_text(" ",strip=True))); k=key(repo)
        if k in seen:continue
        seen.add(k); stars=forks=0; stats=div.find("div",class_=lambda c:c and "tabular-nums" in c)
        if stats:
            st=stats.find("span",class_=lambda c:c and "text-foreground" in c and "font-medium" in c); stars=num(st.get_text(" ",strip=True)) if st else 0
            sp=stats.find_all("span",recursive=False); forks=num(sp[1].get_text(" ",strip=True)) if len(sp)>1 else 0
        de=div.find("p",class_=lambda c:c and "leading-5" in c); desc=clean(de.get_text(" ",strip=True) if de else "")
        topics=[]
        for t in div.find_all("a",href=True):
            if t["href"].startswith("/topics/"):
                v=clean(t.get_text(" ",strip=True).replace("#","")); topics += [v] if v and v not in topics else []
        full=clean(div.get_text(" ",strip=True),2000); m=re.search(r"Featured on GitHub Trending\s+(\d+)\s+times?",full,re.I); dates=ld.get(k,{})
        rows.append(Rec(period,len(rows)+1,repo,stars,forks,int(m.group(1)) if m else 0,desc,topics,bool(div.find(attrs={"aria-label":re.compile("Repository created in",re.I)})),dates.get("created"),dates.get("modified")))
    if len(rows)<MINS[period]:raise RuntimeError(f"Trendshift {period} parse failed: {len(rows)} rows; need {MINS[period]}")
    return rows[:100]

def dated(p):
    m=re.fullmatch(r"(\d{4})年(\d{2})月(\d{2})日\.csv",p.name)
    try:return date(*map(int,m.groups())) if m else None
    except:return None
def previous(root,today):
    a=[(dated(p),p) for p in root.glob("*.csv") if dated(p) and dated(p)<today]; return max(a,default=(None,None))[1]
def readprev(p):
    if not p:return []
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def meta(repos,token,run):
    cache=run/"github-metadata.json"
    if cache.exists():
        try:
            d=json.loads(cache.read_text());
            if d:return d
        except:pass
    s=session(token); s.headers["Accept"]="application/vnd.github+json"; out={}
    for i,repo in enumerate(repos,1):
        r=s.get(f"https://api.github.com/repos/{quote(repo,safe='/')}",timeout=(20,60))
        if r.status_code==200:
            d=r.json(); lic=d.get("license") or {}; out[key(repo)]={"full_name":d.get("full_name") or repo,"description":d.get("description") or "","topics":d.get("topics") or [],"created_at":d.get("created_at"),"updated_at":d.get("updated_at"),"pushed_at":d.get("pushed_at"),"stargazers_count":d.get("stargazers_count") or 0,"archived":bool(d.get("archived")),"disabled":bool(d.get("disabled")),"fork":bool(d.get("fork")),"license_spdx":lic.get("spdx_id")}
        else:out[key(repo)]={"full_name":repo,"error_status":r.status_code}
        if i%40==0:print(f"GitHub metadata {i}/{len(repos)}",flush=True); time.sleep(.4)
    cache.write_text(json.dumps(out,ensure_ascii=False,indent=2)); return out

def text(c):
    x=[c.repo,c.meta.get("description","")]+list(c.meta.get("topics") or [])
    for r in c.trend.values():x += [r.desc]+r.topics
    if c.prev:x += [c.prev.get("项目分类",""),c.prev.get("项目简介","")]
    return " ".join(map(str,x)).lower()
def ai(c):
    t=" "+text(c)+" "; pc=(c.prev or {}).get("项目分类","").lower()
    return any(z in pc for z in ("ai","agent","mcp","rag","llm","模型","语音","视频","视觉","机器人","知识库","记忆","多模态")) or any(z in t for z in AI)
def excluded(c):
    t=text(c); name=c.repo.split("/",1)[-1].lower()
    if name.startswith("awesome"):return True
    if any(z in t for z in BLOCK):return True
    return False
def valid(c,now):
    if c.meta.get("archived") or c.meta.get("disabled") or c.meta.get("fork"):return False
    pushed=iso(c.meta.get("pushed_at") or c.meta.get("updated_at")) or max((iso(r.modified) for r in c.trend.values() if r.modified),default=None)
    if not pushed or (now.astimezone(timezone.utc)-pushed).days>30:return False
    created=iso(c.meta.get("created_at")) or min((iso(r.created) for r in c.trend.values() if r.created),default=None)
    if created and (now.astimezone(timezone.utc)-created).days>366 and not (c.prev and c.trend):return False
    return True
def classify(c):
    t=text(c)
    for cat,ks in RULES:
        if any(k in t for k in ks):return cat
    return "AI 基础设施 / 运行与平台层"
def license(c):
    x=clean(str(c.meta.get("license_spdx") or ""),80)
    if x and x.upper() not in {"NOASSERTION","OTHER","NONE","NULL"}:return x
    x=clean((c.prev or {}).get("项目 License",""),80)
    return x if x and x not in {"NOASSERTION","OTHER","未知","未声明"} else "未知 / 未声明"
def score(c,now):
    if c.trend:
        s=sum(WEIGHTS[p]*max(.01,(101-min(r.rank,100))/100)+(1300 if p=="weekly" else 800 if p=="monthly" else 1800)*min(r.featured,30) for p,r in c.trend.items()); s+=(len(c.trend)-1)*6000+(5000 if len(c.trend)==3 else 0)+(2500 if any(r.new for r in c.trend.values()) else 0); c.tier=3
    elif c.prev:s=13000+max(0,101-int(c.prev.get("排名") or 100))*115; c.tier=2
    else:s=8000;c.tier=1
    s+=min(math.log10(int(c.meta.get("stargazers_count") or 0)+1)*1600,8000)
    p=iso(c.meta.get("pushed_at") or c.meta.get("updated_at")); d=(now.astimezone(timezone.utc)-p).days if p else 99; s+=2800 if d<=2 else 1800 if d<=7 else 900 if d<=14 else 0
    cr=iso(c.meta.get("created_at")); s+=2500 if cr and (now.astimezone(timezone.utc)-cr).days<=366 else 0; s+=1200 if c.prev and c.trend else 0
    return s
def intro(c):
    name=c.repo.split("/",1)[-1]; kind,problem,uses=CAT[c.category]; desc=clean(c.meta.get("description","") or next((r.desc for r in c.trend.values() if r.desc),"提供面向该场景的开源能力"),150)
    zh=len(re.findall(r"[\u4e00-\u9fff]",desc))/max(1,len(desc)); core=(f"核心能力是{desc.rstrip('。.;；')}" if zh>=.15 else f"项目核心能力为“{desc.rstrip('.')}”")
    return clean(f"{name} {kind}，{core}；主要解决{problem}，适合{uses}。",300)
def change(c,rank):
    if not c.prev:return "新上榜"
    d=int(c.prev.get("排名") or rank)-rank; return f"上升{d}" if d>0 else f"下降{-d}" if d<0 else "持平"
def heats(cs):
    a=[c.raw for c in cs]; hi,lo=max(a),min(a); out=[]; last=132001
    for i,v in enumerate(a):
        n=132000-i*700 if hi==lo else round(62000+(v-lo)/(hi-lo)*70000); n=min(n,last-1); n=max(n,62000+len(cs)-i-1); out.append(n); last=n
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",type=Path,default=Path.cwd()); ap.add_argument("--input-dir",type=Path); ap.add_argument("--date"); ap.add_argument("--output",type=Path); a=ap.parse_args()
    root=a.repo_root.resolve(); today=date.fromisoformat(a.date) if a.date else datetime.now(TZ).date(); now=datetime.now(TZ); out=(a.output or root/f"{today:%Y年%m月%d日}.csv").resolve(); prevpath=previous(root,today); prevrows=readprev(prevpath); print("Previous:",prevpath)
    run=a.input_dir.resolve() if a.input_dir else Path(os.environ.get("RUNNER_TEMP",root/".weekly-run"))/today.isoformat(); paths={p:run/f"{p}.html" for p in URLS} if a.input_dir else fetch(run); trend={p:parse(paths[p],p) for p in URLS}; print("Trendshift counts:",{p:len(v) for p,v in trend.items()})
    prevmap={key(r["项目"]):r for r in prevrows}; tm={}; names={}
    for p,rs in trend.items():
        for r in rs:tm.setdefault(key(r.repo),{})[p]=r; names.setdefault(key(r.repo),r.repo)
    keys=list(dict.fromkeys([*tm,*prevmap])); repos=[names.get(k) or prevmap[k]["项目"] for k in keys]; token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and not (run/"github-metadata.json").exists():raise RuntimeError("GITHUB_TOKEN required")
    mm=meta(repos,token or "",run); cs={}
    for k in keys:
        m=mm.get(k,{}); repo=norm(m.get("full_name") or names.get(k) or prevmap.get(k,{}).get("项目","")); ck=key(repo); c=cs.setdefault(ck,Cand(repo)); c.trend.update(tm.get(k,{})); c.meta=m if len(m)>=len(c.meta) else c.meta; c.prev=prevmap.get(k) or c.prev
    q=[]
    for c in cs.values():
        if excluded(c) or not ai(c) or not valid(c,now):continue
        c.category=classify(c); c.license=license(c); c.raw=score(c,now); c.intro=intro(c); q.append(c)
    q.sort(key=lambda c:(c.tier,c.raw,c.repo.lower()),reverse=True)
    if len(q)<100:raise RuntimeError(f"Only {len(q)} qualified repositories; refusing to fabricate Top100")
    q=q[:100]; hs=heats(q); rows=[]
    for i,(c,h) in enumerate(zip(q,hs),1):rows.append(dict(zip(COLS,[i,c.repo,h,change(c,i),c.category,c.license,c.intro])))
    if len({r["项目"].lower() for r in rows})!=100 or [r["排名"] for r in rows]!=list(range(1,101)) or any(rows[i]["热度分"]<=rows[i+1]["热度分"] for i in range(99)):raise RuntimeError("Output validation failed")
    tmp=out.with_suffix(".csv.tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(rows)
    tmp.replace(out); print("Wrote",out)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write(f"output_file={out.relative_to(root).as_posix()}\nprevious_file={(prevpath.relative_to(root).as_posix() if prevpath else '')}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(f"## Weekly GitHub AI Top100\n\n- Output: `{out.name}`\n- Previous: `{prevpath.name if prevpath else 'none'}`\n- Trendshift: monthly={len(trend['monthly'])}, weekly={len(trend['weekly'])}, daily={len(trend['daily'])}\n")
if __name__=="__main__":
    try:main()
    except Exception as e:print(f"ERROR: {e}",file=sys.stderr);raise
