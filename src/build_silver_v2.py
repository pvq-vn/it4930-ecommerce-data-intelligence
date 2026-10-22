"""Create conservative, source-aware normalized Silver v2 tables.

Raw fields remain alongside derived fields. No rows are dropped or imputed.
"""
from pathlib import Path
import json, re

ROOT=Path(__file__).resolve().parents[1]; IN=ROOT/"data"/"staging"; OUT=ROOT/"data"/"silver_v2"; REPORT=ROOT/"reports"

def read(name):
    with (IN/name).open(encoding="utf8") as f: return [json.loads(x) for x in f if x.strip()]
def missing(v): return v is None or (isinstance(v,str) and not v.strip()) or v in ({},[])
def parse_num(v):
    if isinstance(v,(int,float)) and not isinstance(v,bool): return float(v)
    if not isinstance(v,str): return None
    s=v.strip()
    if re.fullmatch(r"-?\d+[.,]\d{1,2}", s): s=s.replace(",", ".")
    else: s=s.replace(".","").replace(",","")
    m=re.search(r"-?\d+(?:\.\d+)?",s)
    return float(m.group()) if m else None

def parse_price_vnd(value, source):
    """Apply the source contract without changing the raw value."""
    if value is None: return None, "FAILED"
    if source in {"cellphones", "tgdd", "fptshop"}:
        if isinstance(value,(int,float)) and not isinstance(value,bool): return float(value), "OK"
        return None, "FAILED"
    if source in {"viettelstore", "hoanghamobile"} and isinstance(value,str):
        cleaned=value.strip().replace("đ","").replace("Đ","").replace("₫","")
        cleaned=cleaned.replace(".","").replace(",","").replace(" ","")
        try: return float(cleaned), "OK"
        except (TypeError,ValueError): return None, "FAILED"
    return None, "FAILED"
def parse_total_sold(value):
    if value is None: return None, "MISSING"
    if isinstance(value,(int,float)) and not isinstance(value,bool): return float(value), "OK"
    if not isinstance(value,str) or not value.strip(): return None, "MISSING"
    s=value.strip().lower().replace('đã bán','').replace('da ban','').strip()
    m=re.search(r'(\d+(?:[.,]\d+)?)\s*(k|nghìn|nghin|m|triệu|trieu)?',s)
    if not m: return None, "FAILED"
    try:
        n=float(m.group(1).replace(',','.'))
        unit=m.group(2)
        if unit=='k' or unit in {'nghìn','nghin'}: n*=1000
        elif unit in {'m','triệu','trieu'}: n*=1000000
        return n, "OK"
    except ValueError: return None, "FAILED"
def text_status(v):
    if v is None: return "NULL"
    if isinstance(v,str) and not v.strip(): return "EMPTY_OR_WHITESPACE"
    return "PRESENT"
def normalize_brand(v):
    if missing(v): return None
    s=str(v).strip()
    key=re.sub(r"[^a-z0-9]+", "", s.lower())
    mapping={
        "apple":"Apple","iphone":"Apple","macbook":"Apple",
        "asus":"ASUS","samsung":"Samsung","xiaomi":"Xiaomi",
        "lenovo":"Lenovo","dell":"Dell","hp":"HP","hewlettpackard":"HP",
        "oppo":"OPPO","realme":"Realme","vivo":"Vivo","nokia":"Nokia",
        "tecno":"Tecno","nubia":"Nubia","redmagic":"Nubia",
        "honor":"Honor","huawei":"Huawei","masstel":"Masstel",
        "acer":"Acer","msi":"MSI","lg":"LG","motorola":"Motorola",
        "oneplus":"OnePlus","tcl":"TCL","infinix":"Infinix",
    }
    return mapping.get(key,s)
def attr_extract(attrs):
    """Conservative extraction from explicit attribute labels only."""
    empty={"installed_ram_gb":None,"max_ram_gb":None,"battery_mah":None,"battery_wh":None,"charger_watt":None,"cpu_norm":None,"gpu_norm":None,"storage_gb":None,"color_norm":None,"screen_size_inch":None,"operating_system_norm":None,"camera_mp":None,"display_type_norm":None,"network_type_norm":None,"hardware_extraction_confidence":"FAILED"}
    if not isinstance(attrs,dict): return empty
    found={"installed_ram_gb":[],"max_ram_gb":[],"battery_mah":[],"battery_wh":[],"charger_watt":[],"storage_gb":[],"screen_size_inch":[],"camera_mp":[]}
    text_found={"cpu_norm":[],"gpu_norm":[],"color_norm":[],"operating_system_norm":[],"display_type_norm":[],"network_type_norm":[]}
    for k,v in attrs.items():
        if not isinstance(v,(str,int,float)) or not str(v).strip(): continue
        key=str(k).lower(); val=str(v)
        if any(t in key for t in ['cpu','bộ xử lý','chip xử lý','loại cpu','chipset','chip']) and not any(t in key for t in ['gpu','đồ họa','đồ hoạ']): text_found['cpu_norm'].append(val.strip())
        if any(t in key for t in ['gpu','card']) and not any(t in val.lower() for t in ['sd card reader','card reader']): text_found['gpu_norm'].append(val.strip())
        if isinstance(v,bool):
            continue
        color_key=any(t in key for t in ['màu','color_name','colorname','colour']) or key in {'color','colour'}
        color_value=val.strip()
        color_noise=('%' in color_value and any(t in color_value.lower() for t in ['ntsc','srgb','dci-p3','p3'])) or any(t in color_value.lower() for t in ['triệu màu','tỷ màu','không công bố','khong cong bo'])
        if color_key and not color_noise and color_value.lower() not in {'true','false','yes','no','không'}: text_found['color_norm'].append(color_value)
        if any(t in key for t in ['hệ điều hành','operating system','os']): text_found['operating_system_norm'].append(val.strip())
        if (any(t in key for t in ['display type','display_type','mobile_type_of_display','t?m n?n','c?ng ngh? m?n h?nh','lo?i m?n h?nh','mÃ n hÃ¬nh','cÃ´ng nghá»‡ mÃ n hÃ¬nh','loáº¡i mÃ n hÃ¬nh','táº¥m ná»�n']) or (any(term.lower() in val.lower() for term in ['amoled','oled','ltpo','ips','lcd','tft','mini led']) and not any(t in key for t in ['gpu','card','đồ họa']))):
            terms=[]
            for term in ['AMOLED','OLED','LTPO','IPS','LCD','TFT','Mini LED','LED']:
                if term.lower() in val.lower(): terms.append(term)
            if terms: text_found['display_type_norm'].append('|'.join(terms))
        if any(t in key for t in ['mạng di động','hỗ trợ mạng','network','5g','4g']) and val.strip().lower() not in {'no_selection','none','n/a'}: text_found['network_type_norm'].append(val.strip())
        nums=re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(gb|mah|wh|w)\b",val.lower())
        for n,u in nums:
            x=float(n.replace('.','').replace(',','')) if u=='mah' else float(n.replace(',','.'))
            if u=='gb' and ('ram' in key or key=='ram'):
                found['max_ram_gb' if any(t in key for t in ['tối đa','toi da','max','hỗ trợ']) else 'installed_ram_gb'].append(x)
            elif u=='mah' and any(t in key for t in ['pin','battery']): found['battery_mah'].append(x)
            elif u=='wh' and any(t in key for t in ['pin','battery']): found['battery_wh'].append(x)
            elif u=='w' and any(t in key for t in ['sạc','sac','charger','công suất']): found['charger_watt'].append(x)
        for n,u in re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(tb|gb|inch|in|mp)\b",val.lower()):
            x=float(n.replace(',','.'))
            if u=='tb' and any(t in key for t in ['ổ cứng','lưu trữ','bộ nhớ','storage','memory']): found['storage_gb'].append(x*1024)
            elif u=='gb' and any(t in key for t in ['ổ cứng','lưu trữ','bộ nhớ trong','storage','memory']): found['storage_gb'].append(x)
            elif u in {'inch','in'} and any(t in key for t in ['màn hình','screen','display','kích thước']): found['screen_size_inch'].append(x)
            elif u=='mp' and any(t in key for t in ['camera','cam']): found['camera_mp'].append(x)
    out={k:(v[0] if len(set(v))==1 else None) for k,v in found.items()}
    if found['battery_mah']:
        valid_mah=[x for x in found['battery_mah'] if x >= 100]
        out['battery_mah']=max(valid_mah) if valid_mah else max(found['battery_mah'])
    for k,v in text_found.items(): out[k]=v[0] if len(set(v))==1 else None
    n=sum(bool(v) for v in found.values())+sum(bool(v) for v in text_found.values()); amb=any(len(set(v))>1 for v in found.values()) or any(len(set(v))>1 for v in text_found.values())
    out['hardware_extraction_confidence']='FAILED' if n==0 else ('AMBIGUOUS' if amb else 'HIGH')
    return out
def availability(v, source=None):
    if missing(v): return "unknown"
    s=str(v).strip().lower()
    if source == "cellphones":
        try:
            code=int(v)
            return "in_stock" if code == 1 else ("out_of_stock" if code == 0 else "unknown")
        except (TypeError,ValueError): return "unknown"
    if source == "tgdd":
        if "outofstock" in s or "out of stock" in s: return "out_of_stock"
        if "instock" in s or "in stock" in s: return "in_stock"
    if source == "fptshop":
        if s == "mua ngay": return "in_stock"
        return "unknown"
    if source == "hoanghamobile" and s == "sẵn hàng": return "in_stock"
    if source == "viettelstore":
        if s == "còn hàng": return "in_stock"
        if s == "tạm hết hàng": return "out_of_stock"
    if any(x in s for x in ["hết hàng","het hang","out of stock"]): return "out_of_stock"
    if any(x in s for x in ["còn hàng","con hang","in stock","sẵn hàng","san hang"]): return "in_stock"
    return "unknown"
def write(name, rs):
    with (OUT/name).open("w",encoding="utf8",newline="\n") as f:
        for r in rs: f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")
def main():
    ps=read("products_staging.jsonl"); rs=read("reviews_staging.jsonl"); replies=read("review_replies_staging.jsonl")
    products=[]
    for r in ps:
        x=dict(r); p,p_status=parse_price_vnd(r.get("price_raw"),r.get("source")); op,op_status=parse_price_vnd(r.get("original_price_raw"),r.get("source")); rating=parse_num(r.get("rating_raw"))
        # Product-source rating 0 is a no-rating sentinel, not a zero-star score.
        rating_norm=rating if rating is not None and 0<rating<=5 else None
        review_count_norm=None if r.get("source") in {"fptshop","hoanghamobile"} else parse_num(r.get("review_count_raw"))
        sold,sold_status=parse_total_sold(r.get("total_sold_raw")); attrs=attr_extract(r.get("attributes_raw"));
        if attrs.get("color_norm") is None and isinstance(r.get("variant_color_raw"),str) and r.get("variant_color_raw").strip(): attrs["color_norm"]=r.get("variant_color_raw").strip()
        x.update({"brand_norm":normalize_brand(r.get("brand_raw")),"price_vnd":p,"price_parse_status":p_status,"original_price_vnd":op,"original_price_parse_status":op_status,"price_normalized":p,"original_price_normalized":op,"price_missing_reason":None if p_status=="OK" else "FAILED","is_price_missing":p==0,"original_price_missing_reason":None if op_status=="OK" else "FAILED","availability_status":availability(r.get("availability_raw"),r.get("source")),"rating_norm":rating_norm,"rating_normalized":rating_norm,"rating_normalized_status":("MISSING" if rating_norm is None else "VALID_0_5"),"has_rating":False if r.get("source")=="hoanghamobile" or rating_norm is None or rating_norm==0 else True,"review_count_normalized":review_count_norm,"total_sold_normalized":sold,"total_sold_parse_status":sold_status,"discount_rate":((op-p)/op if p is not None and op is not None and op>0 and p>=0 and p<=op else None),"discount_status":("VALID" if p is not None and op is not None and op>0 and 0<=p<=op else "NOT_COMPUTED"),"silver_version":"tv2-silver-2.0",**attrs})
        products.append(x)
    reviews=[]
    for r in rs:
        text_value=r.get("review_text_raw"); usable=r.get("source")!="viettelstore" and isinstance(text_value,str) and bool(text_value.strip())
        x=dict(r); x.update({"review_text_normalized":None if missing(text_value) else str(text_value).strip(),"review_text_status":text_status(text_value),"review_time_status":"MISSING" if missing(r.get("review_time_raw")) else "PRESENT","review_usable":usable,"silver_version":"tv2-silver-2.0"}); reviews.append(x)
    replies_out=[dict(r, silver_version="tv2-silver-2.0") for r in replies]
    OUT.mkdir(parents=True,exist_ok=True); REPORT.mkdir(exist_ok=True); write("products_silver_v2.jsonl",products); write("reviews_silver_v2.jsonl",reviews); write("review_replies_silver_v2.jsonl",replies_out)
    report={"pipeline_stage":"silver_v2","rows":{"products":len(products),"reviews":len(reviews),"replies":len(replies_out)},"rows_dropped":0,"values_imputed":0,"raw_fields_preserved":True,"price_normalized_missing":sum(x["price_normalized"] is None for x in products),"discount_valid":sum(x["discount_status"]=="VALID" for x in products),"rating_valid":sum(x["rating_normalized_status"]=="VALID_0_5" for x in products),"review_text_usable":sum(x["review_text_status"]=="PRESENT" for x in reviews),"notes":["Normalized fields are derived; raw fields remain.","No missing value was imputed and no row was removed."]}
    (REPORT/"silver_v2_quality_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8"); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
