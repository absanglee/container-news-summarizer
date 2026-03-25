"""
Container Ship News Summarizer
기사 제목 입력 -> Gemini가 웹 검색 -> 컨테이너선 관련만 한국어 요약
"""

import os
import json
import re
from datetime import datetime

import streamlit as st
import google.generativeai as genai
# ── API 키 ──────────────────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="🚢 Container Ship News Summarizer",
    page_icon="🚢",
    layout="wide",
)
st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 800;
        color: #1a73e8;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        text-align: center;
        color: #666;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .article-card {
        background: #f8faff;
        border-left: 5px solid #1a73e8;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.2rem;
    }
    .not-relevant-card {
        background: #fff8f8;
        border-left: 5px solid #ccc;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin-bottom: 0.8rem;
    }
    .badge {
        display: inline-block;
        background: #e8f0fe;
        color: #1a73e8;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.8rem;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .score-high { color: #2e7d32; font-weight: bold; }
    .score-mid  { color: #f57c00; font-weight: bold; }
    .score-low  { color: #c62828; font-weight: bold; }
    .korean-summary {
        background: #fff;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        margin-top: 0.7rem;
        font-size: 0.97rem;
        line-height: 1.7;
        color: #222;
    }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🚢 Container Ship News Summarizer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">기사 제목을 입력하면 Gemini AI가 웹에서 직접 검색하여 컨테이너선 관련 기사를 한국어로 요약합니다</div>', unsafe_allow_html=True)
st.divider()


# ── Gemini 모델 ──────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
@st.cache_resource
def get_model():
    api_key = get_api_key()
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config={
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        },
        tools="google_search_retrieval",
    )


# ── 프롬프트 ─────────────────────────────────────────────────
def build_prompt(titles):
    titles_text = "\n".join(f"{i+1}. {t.strip()}" for i, t in enumerate(titles))
    return f"""You are a maritime shipping news analyst.

For each article title below:
1. Search the web for the headline and read only the first 2-3 paragraphs.
2. Check if it is about container ships or boxships (orders, deliveries, charter rates, TEU, MSC/Maersk/COSCO/Evergreen/CMA CGM/ONE/HMM, newbuilds, scrapping, container ports).
3. If relevant, summarize in Korean in 2 sentences max.
4. If not relevant, mark as false.

Return ONLY a JSON array, no markdown:
[{{"article_number":1,"input_title":"...","found_title":"...","source_url":"...","is_relevant":true,"relevance_score":0.95,"key_topics":["topic1"],"korean_summary":"2문장 이내 한국어 요약.","not_relevant_reason":""}}]

TITLES:
{titles_text}
"""


# ── 분석 실행 ────────────────────────────────────────────────
def analyze_titles(model, titles):
    prompt = build_prompt(titles)
    with st.spinner("🔍 Gemini가 웹에서 기사를 검색하고 분석 중입니다... (잠시 기다려 주세요)"):
        response = model.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        st.warning("⚠️ JSON 파싱 오류. AI 원본 응답:")
        st.code(raw[:3000], language="text")
        return []

# ── 보고서 생성 ──────────────────────────────────────────────
def make_txt_report(articles):
    relevant = [a for a in articles if a.get("is_relevant")]
    lines = [
        "=" * 60,
        "  컨테이너선 / 박스선 뉴스 요약 보고서",
        f"  생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  입력 기사: {len(articles)}건 / 관련 기사: {len(relevant)}건",
        "=" * 60,
        "",
    ]
    for art in relevant:
        lines += [
            f"【기사 #{art.get('article_number', '?')}】",
            f"입력 제목: {art.get('input_title', 'N/A')}",
            f"실제 제목: {art.get('found_title', 'N/A')}",
            f"출처 URL: {art.get('source_url', 'N/A')}",
            f"관련도: {art.get('relevance_score', 0):.0%}",
            f"토픽: {', '.join(art.get('key_topics', []))}",
            "",
            f"한국어 요약:",
            f"{art.get('korean_summary', 'N/A')}",
            "",
            "-" * 60,
            "",
        ]
    return "\n".join(lines)

# ── 메인 UI ──────────────────────────────────────────────────
model = get_model()

if not model:
    st.error("❌ GEMINI_API_KEY가 설정되어 있지 않습니다.")
    st.info("👉 Streamlit Cloud → App settings → Secrets 에서 GEMINI_API_KEY를 입력해주세요.")
    st.stop()
with st.sidebar:
    st.markdown("### ℹ️ 사용 방법")
    st.markdown("""
1. 기사 제목을 **한 줄에 하나씩** 입력
2. **분석 시작** 버튼 클릭
3. Gemini가 웹에서 기사 직접 검색
4. 컨테이너선 관련 기사만 한국어 요약
5. 결과 다운로드
    """)
    st.divider()
    st.markdown("### 🏷️ 탐지 기준")
    st.markdown("""
- Container ship / Boxship
- 컨테이너선 발주 / 용선 / 인도
- TEU 용량 관련
- MSC, Maersk, COSCO
- Evergreen, CMA CGM
- ONE, HMM, Yang Ming
- 컨테이너 항만 처리량
    """)
    st.divider()
    st.caption(f"🤖 모델: {GEMINI_MODEL}")
    st.caption("🌐 Google Search 연동")
st.markdown("### 📝 기사 제목 입력")
st.caption("한 줄에 하나씩 입력하세요. 영문 제목 그대로 붙여넣기 하시면 됩니다.")

titles_input = st.text_area(
    label="기사 제목 목록",
    placeholder="MSC orders 10 ultra-large containerships at CSSC\nMaersk reports Q3 earnings amid freight rate pressure\nEvergreen takes delivery of 16,000 TEU vessel",
    height=220,
    label_visibility="collapsed",
)
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")
if run_btn:
    raw_titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]

    if not raw_titles:
        st.warning("⚠️ 기사 제목을 입력해주세요.")
        st.stop()

    if len(raw_titles) > 20:
        st.warning("⚠️ 한 번에 최대 20개까지 입력 가능합니다.")
        raw_titles = raw_titles[:20]

    st.info(f"📋 총 **{len(raw_titles)}개** 기사 제목을 분석합니다.")

    try:
        articles = analyze_titles(model, raw_titles)
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            st.error("❌ Gemini API 한도 초과입니다. 잠시 후 다시 시도해주세요.")
        else:
            st.error(f"❌ 오류 발생: {e}")
        st.stop()
    
    if not articles:
        st.error("❌ 결과를 가져오지 못했습니다. 다시 시도해주세요.")
        st.stop()

    relevant = [a for a in articles if a.get("is_relevant")]
    not_relevant = [a for a in articles if not a.get("is_relevant")]

    st.divider()
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("📋 입력 기사", f"{len(articles)}건")
    col_b.metric("✅ 관련 기사", f"{len(relevant)}건")
    col_c.metric("❌ 비관련 기사", f"{len(not_relevant)}건")
    col_d.metric("📅 분석 시각", datetime.now().strftime("%H:%M:%S"))
    st.divider()
    if relevant:
        st.markdown(f"### ✅ 컨테이너선 관련 기사 — {len(relevant)}건")
        for art in relevant:
            score = art.get("relevance_score", 0)
            score_pct = f"{score:.0%}"
            score_class = "score-high" if score >= 0.8 else "score-mid" if score >= 0.5 else "score-low"
            topics_html = "".join(
                f'<span class="badge">{t}</span>' for t in art.get("key_topics", [])
            )
            url = art.get("source_url", "")
            url_html = f'<a href="{url}" target="_blank" style="font-size:0.8rem;color:#1a73e8;">🔗 원문 보기</a>' if url else ""
            st.markdown(f"""
<div class="article-card">
    <div style="font-size:1.05rem;font-weight:700;color:#1a73e8;margin-bottom:0.4rem;">
        📰 기사 #{art.get('article_number','?')} &nbsp;
        <span style="font-size:0.85rem;color:#666;">
            관련도: <span class="{score_class}">{score_pct}</span>
        </span>
    </div>
    <div style="color:#333;margin-bottom:0.2rem;">
        <b>입력 제목:</b> {art.get('input_title','N/A')}
    </div>
    <div style="color:#555;font-size:0.9rem;margin-bottom:0.4rem;">
        <b>실제 제목:</b> {art.get('found_title','N/A')} &nbsp; {url_html}
    </div>
    <div style="margin-bottom:0.5rem;">{topics_html}</div>
    <div class="korean-summary">
        📝 <b>한국어 요약</b><br><br>
        {art.get('korean_summary','N/A')}
    </div>
</div>
""", unsafe_allow_html=True)

    else:
        st.warning("⚠️ 컨테이너선 또는 박스선 관련 기사가 발견되지 않았습니다.")
    if not_relevant:
        with st.expander(f"❌ 비관련 기사 — {len(not_relevant)}건 (클릭하여 펼치기)"):
            for art in not_relevant:
                st.markdown(f"""
<div class="not-relevant-card">
    <div style="color:#888;font-size:0.9rem;">
        <b>#{art.get('article_number','?')}</b> {art.get('input_title','N/A')}
        &nbsp;→&nbsp;
        <span style="color:#c62828;">{art.get('not_relevant_reason','관련 없음')}</span>
    </div>
</div>
""", unsafe_allow_html=True)
    if relevant:
        st.divider()
        st.markdown("### 💾 결과 저장")
        col_d, col_e = st.columns(2)

        txt_data = make_txt_report(articles)
        col_d.download_button(
            label="📥 TXT 보고서 다운로드",
            data=txt_data.encode("utf-8"),
            file_name=f"컨테이너뉴스_요약보고서_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

        json_data = json.dumps(articles, ensure_ascii=False, indent=2)
        col_e.download_button(
            label="📥 JSON 데이터 다운로드",
            data=json_data.encode("utf-8"),
            file_name=f"컨테이너뉴스_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )


   






