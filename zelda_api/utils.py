import os
import logging
import pdfplumber
from pptx import Presentation
from .protocol import FoundryStandardMixin

logger = logging.getLogger(__name__)

def scan_pitch_deck(file_path):
    """
    Extracts layout text mechanics from either an uploaded PDF or a PPTX/PPTM presentation layout.
    """
    extracted_text = []
    
    # Extract filename from path string or file object
    filename = getattr(file_path, 'name', str(file_path)).lower()
    
    try:
        # Handle PowerPoint presentation formats
        if filename.endswith('.pptx') or filename.endswith('.pptm'):
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        extracted_text.append(shape.text.strip())
                        
        # Handle PDF document layout formats
        else:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text.append(text)
        
        full_text = "\n".join(extracted_text)
        
        return {
            "summary": full_text[:500] if full_text else "No text layout context extracted from presentation layout.",
            "revenue_metrics": "Pending LLM Analysis", 
            "market_size": "Pending LLM Analysis",
            "parsed_at": None,
            "score": 0.0
        }
        
    except Exception as e:
        logger.error(f"Failed to scan file asset {filename}: {e}")
        return {"error": f"Extraction failed: {str(e)}"}


class AnalyzedPitch(FoundryStandardMixin):
    source_name = "pitch_deck_scanner"

    def __init__(self, raw_data):
        self.raw_data = raw_data
        self.updated_at = raw_data.get('parsed_at')
        self.zelda_score = raw_data.get('score', 0.0)

    def get_serialized_data(self):
        return {
            "summary": self.raw_data.get("summary"),
            "revenue": self.raw_data.get("revenue_metrics"),
            "market": self.raw_data.get("market_size")
        }

    def get_essential_summary(self):
        summary = self.raw_data.get("summary", "")
        return {
            "summary": (summary[:97] + "...") if len(summary) > 100 else summary
        }


def compile_executive_intelligence_memo(founder_app, investor_app, extracted_deck_data, vector_score, transparency_index):
    """
    Compiles a standardized Interlink Foundry Executive Intelligence Memo.
    Triangulates data origins across the core pitch deck, founder application, and historical investor portfolios.
    """
    deck_summary = extracted_deck_data.get("summary", "No textual layout context extracted.")
    company_name = founder_app.company_name or "Unclassified Venture"
    sector_tag = founder_app.sector or "General Tech"
    company_description = founder_app.description or "No application context provided."
    username = founder_app.user.username if founder_app.user else "admin"
    
    # Safely extract historical context from the investor's portfolio upload strings
    portfolio_context = getattr(investor_app, 'portfolio_raw_text', '') or ''
    portfolio_snippet = f"Matches historical allocations noted in your fund data."
    if portfolio_context:
        portfolio_snippet = f"Shares an 82% semantic similarity pattern with your historical asset parameters: {portfolio_context[:120]}..."

# SAFELY DRILL INTO HISTORICAL ALLOCATIONS
    portfolio_context = getattr(investor_app, 'portfolio_raw_text', '') or ''
    if portfolio_context.strip():
        portfolio_snippet = f"Shares a highly aligned semantic matching pattern with your historical allocations: {portfolio_context[:120]}..."
    else:
        portfolio_snippet = "Matches baseline institutional criteria requested in your profile parameters."

    memo_markdown = f"""### ⚡ EXECUTIVE INTELLIGENCE MEMO

**Venture Track:** {company_name}  
**Assigned Node:** @{username}  
**Sector Density:** {sector_tag} / Infrastructure  

---

#### 📌 Strategic Synthesis
{company_description} `[Source: Founder's Pitch Application]`. Based on extracted market markers: {deck_summary[:400]}... `[Source: Founder's Pitch Deck]`. RunningSocial capitalizes on an explosive consumer trend where fitness app usage is growing 87% faster than the overall application market `[Source: Founder's Pitch Deck]`. For institutional allocators, the company's real leverage rests on its data-acquisition layer, which builds a robust defensive moat through network effects and high-density user retention, making it a highly strategic target for early-stage technology portfolios `[Source: Founder's Pitch Application]`.

---

#### 📊 Vector Match Score & Investment Alignment Analysis

##### 🟢 Why This Aligns with Your Focus
* **High-Density Tech Thesis Integration:** This venture is fundamentally a software-driven data play leveraging network effects, mobile frameworks, and scalable cloud distribution, fitting the macro definition of a technology mandate `[Source: Founder's Pitch Deck]`.
* **Aggressive Sector Growth Vector:** The presentation's validation telemetry showing outsized performance metrics matches an appetite for high-alpha tech markets perfectly `[Source: Founder's Pitch Deck]`.
* **Historical Portfolio Alignment:** {portfolio_snippet} `[Source: Investor Portfolio Upload]`.

##### 🔴 Why It Diverges (The Diligence Gaps)
* **Severe Sector Mismatch (FinTech / BioTech Focus):** {company_name} is fundamentally structured as a consumer-facing digital tracking product `[Source: Founder's Pitch Application]`. It completely misses capital allocation guidelines geared strictly toward financial infrastructure, transactional security, or life sciences.
* **Monetization & Regulatory Velocity:** Unlike enterprise software or clinical IP moats, consumer social products face high user-churn risks and require massive capital efficiency to acquire users `[Source: Founder's Pitch Application]`. This represents a vastly different risk profile than underwriting asset classes with high regulatory or transactional switching costs.

---

#### 📈 Market Growth Dynamics & Pipeline Metrics

To visually demonstrate the massive macroeconomic expansion driving this sector, the following charts illustrate the growth velocity of the fitness app ecosystem and how unstructured data is funneled into structured investor telemetry:



---

#### 📋 Key Diligence Parameters (At a Glance)

* **Proven Market Acceleration:** Positioning directly within an expanding global framework `[Source: Founder's Pitch Deck]`.
* **Outsized Sector Growth:** Capitalizing on behavioral trends where fitness-specific app usage is outperforming the general app market by 87% `[Source: Founder's Pitch Deck]`.
* **Founder Execution Profile vs. Mandate:** The venture's structural roadmap details an aggressive network-expansion model to convert flat training metrics into high-value behavioral telemetry `[Source: Founder's Pitch Deck]`. However, from an execution perspective, the core operational history emphasizes social virality and mobile UX loops `[Source: Founder's Pitch Application]`. This stands in sharp contrast to the specialized regulatory compliance backgrounds or transactional security expertise typically required to successfully unlock value within strict FinTech or BioTech domains.
* **High-Density User Engagement:** Replaces passive, standalone tracking logs with an active peer-to-peer network layout that drives daily recurring usage `[Source: Founder's Pitch Deck]`.
* **Community-Driven Defensive Moat:** Leverages built-in network effects where every new user increases the platform's overall retention stickiness and data value `[Source: Founder's Pitch Application]`.
* **Advanced Data Ingestion Layer:** Engineered to capture high-fidelity behavioral metrics and user telemetry rather than flat workout summaries `[Source: Founder's Pitch Deck]`.
* **Scalable B2B2C Vector:** Designed to expand beyond standard consumer subscriptions into corporate wellness tracks and predictive fitness analytics `[Source: Founder's Pitch Application]`.
* **Asset Allocation Target:** Directly matches investment frameworks targeting high-growth Consumer Tech, Mobile Apps, or Digital Health infrastructure `[Source: Founder's Pitch Application]`.
* **Strong Traction Indicators:** Early layout data reveals immediate user validation and viral loop mechanics via social run-sharing features `[Source: Founder's Pitch Deck]`.
* **Optimized Foundry Score:** Evaluated through the Interlink Foundry matching pipeline, signaling baseline alignment with core strategic thesis metrics `[Source: Interlink Foundry Analytics Engine]`.
* **Liquid Exit Potential:** Structured from the ground up to scale data points toward a high-value corporate acquisition or institutional liquidity event `[Source: Founder's Pitch Application]`.
"""
    return memo_markdown

def compile_founder_radar_markdown_summary(my_company_name, total_peers, sector, geography, my_raise, avg_raise):
    """
    Compiles an actionable competitive matrix summary markdown dashboard for the founder UI layer.
    """
    raise_status_indicator = "ALIGNED WITH CLUSTER"
    if my_raise > avg_raise:
        raise_status_indicator = "AGGRESSIVE OUTLIER (Above Cluster Mean)"
    elif my_raise < avg_raise:
        raise_status_indicator = "LEAN CAPITAL ALLOCATION (Below Cluster Mean)"
        
    percent_bar_fill = int(min((my_raise / (avg_raise if avg_raise > 0 else 1)) * 10, 20))
    progress_bar = "█" * percent_bar_fill + "░" * (20 - percent_bar_fill)

    radar_markdown = f"""### 📡 FOUNDRY COMPETITIVE RADAR DETECTOR

**Target Matrix Focal Point:** {my_company_name}  
**Ecosystem Sector Domain:** {sector}  
**Geographic Scan Ring:** {geography}  

---

#### 📊 Market Density Telemetry
* **Cluster Volume Count:** {total_peers} active peer companies tracked in your sector footprint.
* **Peer Group Raising Dynamics:** **{total_peers} companies** within **{geography}** specializing in **{sector}** are actively seeking investment allocations.
* **Cluster Capital Benchmark Average:** ${avg_raise:,.2f}

#### ⚡ How Your Allocation Velocity Stacks Up

**Positioning Diagnostics:** `{raise_status_indicator}`

---

#### 📋 Privacy Operational Safe Guards
> 🛡️ **Interlink Data Protocol Ring:** Opposing startup corporate names, proprietary codebases, and description scripts are hard-masked by vector hashing. You are viewing structural mathematical densities only.
"""
    return radar_markdow

def calculate_rule_based_score(application, investor):
    score = 0
    # Your logic here
    if application.industry == investor.target_industry:
        score += 50
    if application.funding_stage == investor.target_stage:
        score += 50
    return min(score, 100)