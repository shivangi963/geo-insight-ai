from __future__ import annotations

import os
import re
import math
from typing import Dict, Any, List, Optional, Tuple
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


def _safe(value: Any, fallback: Any = None) -> Any:

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return fallback
        return value
    if isinstance(value, dict):
        return {k: _safe(v, fallback) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v, fallback) for v in value]
    return value

GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai
    _api_key = os.getenv("GOOGLE_API_KEY", "")
    if _api_key and _api_key != "your_key_here":
        genai.configure(api_key=_api_key)
        GEMINI_AVAILABLE = True
        print("Gemini API configured")
except Exception as _e:
    print(f"[WARNING] Gemini not available: {_e}")


def _npv(rate: float, cash_flows: List[float]) -> float:
 
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _irr(cash_flows: List[float], guess: float = 0.10, max_iter: int = 1000) -> Optional[float]:
    
    if not cash_flows or cash_flows[0] >= 0:
        return None

    rate = guess
    for _ in range(max_iter):
        npv_val  = _npv(rate, cash_flows)
        dnpv_val = sum(-t * cf / (1 + rate) ** (t + 1)
                       for t, cf in enumerate(cash_flows))
        if abs(dnpv_val) < 1e-12:
            break
        new_rate = rate - npv_val / dnpv_val
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate
    return None


def _monthly_mortgage(principal: float, annual_rate: float, years: int) -> float:
   
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

_SUFFIX = {
    'k': 1_000, 'K': 1_000,
    'l': 1_00_000, 'L': 1_00_000,      
    'cr': 1_00_00_000, 'Cr': 1_00_00_000,   
    'crore': 1_00_00_000,
    'm': 1_000_000, 'M': 1_000_000,
}

_SUFFIX_PATTERN = re.compile(
    r'(?:Rs\.?\s*)?(\d{1,3}(?:[,\d]*)?(?:\.\d+)?)\s*'
    r'(crore|lakh|lac|Cr|cr|L|l|K|k|M|m)\b',
    re.IGNORECASE
)
_PLAIN_PATTERN = re.compile(r'(?<!\d)(\d{4,})(?!\d)')


def _parse_indian_number(text: str) -> Optional[float]:

    text = text.replace(',', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


def extract_labeled_numbers(query: str) -> Dict[str, Optional[float]]:
  
    q = query.lower()
    result: Dict[str, Optional[float]] = {
        'price': None,
        'rent': None,
        'down_pct': None,
        'expense_ratio': None,
        'interest_rate': None,
        'loan_term': None,
        'holding_years': None,
        'appreciation_rate': None,
    }

    tagged: List[Tuple[float, int]] = []   

    for m in _SUFFIX_PATTERN.finditer(query):
        raw = m.group(1).replace(',', '')
        suffix = m.group(2)
        multiplier = _SUFFIX.get(suffix, _SUFFIX.get(suffix.lower(), 1))
        try:
            tagged.append((float(raw) * multiplier, m.start()))
        except ValueError:
            pass

    covered = {pos for _, pos in tagged}

    for m in _PLAIN_PATTERN.finditer(query):
        if m.start() not in covered:
            try:
                tagged.append((float(m.group(1).replace(',', '')), m.start()))
            except ValueError:
                pass

    tagged.sort(key=lambda x: x[1])  


    WINDOW = 40   

    def _ctx(pos: int) -> str:
        return query[max(0, pos - WINDOW): pos + WINDOW].lower()

    price_kw    = ('price', 'worth', 'cost', 'buy', 'purchase', 'value',
                   'property', 'flat', 'house', 'apartment', 'bhk')
    rent_kw     = ('rent', 'rental', 'monthly', 'income', 'lease', 'renting')
    down_kw     = ('down', 'downpayment', 'deposit', 'equity', '%')
    expense_kw  = ('expense', 'operating', 'opex', 'cost ratio', 'vacancy')
    rate_kw     = ('interest', 'rate', 'roi', '%', 'percent', 'loan rate')
    term_kw     = ('year', 'yr', 'term', 'tenure', 'years')
    hold_kw     = ('hold', 'holding', 'sell after', 'exit')
    appr_kw     = ('appreciat', 'growth', 'capital gain')

    def _best_match(keywords, exclude_positions) -> Optional[float]:
  
        best_val, best_score = None, 0
        for val, pos in tagged:
            if pos in exclude_positions:
                continue
            ctx = _ctx(pos)
            score = sum(1 for kw in keywords if kw in ctx)
            if score > best_score:
                best_score, best_val = score, val
        return best_val if best_score > 0 else None

    used: set = set()

    down_match = re.search(r'(\d{1,2})\s*%?\s*down', q)
    if down_match:
        result['down_pct'] = float(down_match.group(1))
        # find and exclude this position
        for val, pos in tagged:
            if abs(val - result['down_pct']) < 0.01:
                used.add(pos)

    rate_match = re.search(
        r'(\d{1,2}(?:\.\d+)?)\s*%?\s*(?:interest|loan rate|rate of interest)', q
    ) or re.search(r'(?:interest|rate)\s*(?:of\s*)?(?:interest\s*)?(?:is\s*)?(\d{1,2}(?:\.\d+)?)\s*%', q)
    if rate_match:
        result['interest_rate'] = float(rate_match.group(1))

    term_match = re.search(r'(\d{1,2})\s*(?:year|yr|years)\s*(?:loan|tenure|term)', q)
    if term_match:
        result['loan_term'] = float(term_match.group(1))

    hold_match = re.search(
        r'(?:hold|sell after|holding period of?)\s*(\d{1,2})\s*(?:year|yr)', q
    )
    if hold_match:
        result['holding_years'] = float(hold_match.group(1))

    appr_match = re.search(
        r'(\d{1,2}(?:\.\d+)?)\s*%?\s*(?:appreciat|capital growth|value growth)', q
    ) or re.search(r'appreciat\w*\s*(?:of|at|@)?\s*(\d{1,2}(?:\.\d+)?)', q)
    if appr_match:
        result['appreciation_rate'] = float(appr_match.group(1))

    expense_match = re.search(r'(\d{1,2}(?:\.\d+)?)\s*%?\s*(?:expense|opex|operating)', q)
    if expense_match:
        result['expense_ratio'] = float(expense_match.group(1)) / 100

    result['rent']  = _best_match(rent_kw,  used)
    if result['rent']:
        for val, pos in tagged:
            if abs(val - result['rent']) < 0.01:
                used.add(pos)

    result['price'] = _best_match(price_kw, used)
    if result['price']:
        for val, pos in tagged:
            if abs(val - result['price']) < 0.01:
                used.add(pos)


    remaining = [(v, p) for v, p in tagged if p not in used]
    if result['price'] is None and result['rent'] is None and len(remaining) >= 2:

        vals = sorted([v for v, _ in remaining], reverse=True)
        result['price'] = vals[0]
        result['rent']  = vals[1] if len(vals) > 1 else None
    elif result['price'] is None and remaining:
        result['price'] = remaining[0][0]
    elif result['rent'] is None and remaining:
        result['rent'] = remaining[0][0]

    return result

class InvestmentAnalyzer:

    DEFAULT_DOWN_PCT      = 20.0    
    DEFAULT_INTEREST_RATE = 8.5   
    DEFAULT_LOAN_TERM     = 20    
    DEFAULT_EXPENSE_RATIO = 0.30    
    DEFAULT_CLOSING_COSTS = 0.07   
    DEFAULT_CAPEX_RESERVE = 0.01    
    DEFAULT_HOLDING_YEARS = 10
    DEFAULT_APPRECIATION  = 5.0    

    def compute(
        self,
        price: float,
        monthly_rent: float,
        down_pct: float             = DEFAULT_DOWN_PCT,
        interest_rate: float        = DEFAULT_INTEREST_RATE,
        loan_term: int              = DEFAULT_LOAN_TERM,
        expense_ratio: float        = DEFAULT_EXPENSE_RATIO,
        holding_years: int          = DEFAULT_HOLDING_YEARS,
        appreciation_rate: float    = DEFAULT_APPRECIATION,
        closing_cost_pct: float     = DEFAULT_CLOSING_COSTS,
        capex_pct: float            = DEFAULT_CAPEX_RESERVE,
    ) -> Dict[str, Any]:
        

      
        down_payment   = price * (down_pct / 100)
        closing_costs  = price * closing_cost_pct
        annual_capex   = price * capex_pct
        total_invested = down_payment + closing_costs          
        loan_amount    = price - down_payment

        monthly_emi    = _monthly_mortgage(loan_amount, interest_rate, loan_term)
        annual_dscr    = monthly_emi * 12                    

        annual_rent     = monthly_rent * 12
        annual_opex     = annual_rent * expense_ratio          
        annual_noi      = annual_rent - annual_opex          
        annual_capex_rs = annual_capex
        annual_cf       = annual_noi - annual_dscr - annual_capex_rs   
        monthly_cf      = annual_cf / 12

    
        gross_yield     = (annual_rent / price) * 100

        cap_rate        = (annual_noi / price) * 100

        coc_roi         = (annual_cf / total_invested) * 100 if total_invested > 0 else 0

      
        monthly_opex    = annual_opex / 12
        beo             = ((monthly_emi + monthly_opex) / monthly_rent * 100
                           if monthly_rent > 0 else 100.0)
        beo             = min(beo, 100.0)

        dscr            = annual_noi / annual_dscr if annual_dscr > 0 else None


        payback_years   = total_invested / annual_cf if annual_cf > 0 else None


        future_value    = price * (1 + appreciation_rate / 100) ** holding_years
        equity_gain     = future_value - price       
        loan_balance    = _remaining_balance(
            loan_amount, interest_rate, loan_term, holding_years
        )
        net_sale_proceeds = future_value - loan_balance  

       
        cf_series: List[float] = [-total_invested]
        for yr in range(1, holding_years + 1):
            if yr < holding_years:
                cf_series.append(annual_cf)
            else:
                cf_series.append(annual_cf + net_sale_proceeds)

        irr_val = _irr(cf_series)

        one_pct_rule_target = price * 0.01    
        one_pct_ratio       = (monthly_rent / one_pct_rule_target
                                if one_pct_rule_target > 0 else 0)

        return {
         
            'price':             price,
            'monthly_rent':      monthly_rent,
            'down_pct':          down_pct,
            'down_payment':      down_payment,
            'closing_costs':     closing_costs,
            'total_invested':    total_invested,
            'loan_amount':       loan_amount,
            'interest_rate':     interest_rate,
            'loan_term':         loan_term,
            'expense_ratio':     expense_ratio,
            'holding_years':     holding_years,
            'appreciation_rate': appreciation_rate,
           
            'monthly_emi':       monthly_emi,
            'monthly_opex':      monthly_opex,
            'monthly_cf':        monthly_cf,
         
            'annual_rent':       annual_rent,
            'annual_opex':       annual_opex,
            'annual_noi':        annual_noi,
            'annual_capex':      annual_capex_rs,
            'annual_cf':         annual_cf,
            'annual_debt':       annual_dscr,
     
            'gross_yield':       gross_yield,
            'cap_rate':          cap_rate,
            'coc_roi':           coc_roi,
            'break_even_occ':    beo,
            'dscr':              dscr,
            'payback_years':     payback_years,
            'one_pct_ratio':     one_pct_ratio,
    
            'future_value':      future_value,
            'equity_gain':       equity_gain,
            'loan_balance_exit': loan_balance,
            'net_sale_proceeds': net_sale_proceeds,
        
            'irr':               irr_val,
        }


def _remaining_balance(principal: float, annual_rate: float,
                       total_years: int, years_elapsed: int) -> float:
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    n = total_years * 12
    p = years_elapsed * 12
    if p >= n:
        return 0.0
    return principal * ((1 + r) ** n - (1 + r) ** p) / ((1 + r) ** n - 1)



def _rs(amount: float) -> str:
  
    if abs(amount) >= 1_00_00_000:
        return f"Rs. {amount / 1_00_00_000:.2f} Cr"
    if abs(amount) >= 1_00_000:
        return f"Rs. {amount / 1_00_000:.2f} L"
    return f"Rs. {amount:,.0f}"


def _pct(val: float) -> str:
    return f"{val:.2f}%"


def _dscr_label(dscr: Optional[float]) -> str:
    if dscr is None:    return "N/A (no loan)"
    if dscr >= 1.5:     return "Excellent (lender-safe)"
    if dscr >= 1.25:    return "Good (lender threshold)"
    if dscr >= 1.0:     return "Marginal (tight)"
    return "Poor (NOI < debt service)"


def _quality_badge(coc: float, dscr: Optional[float], cf: float) -> Tuple[str, str]:

    if cf < 0:
        return ("NEGATIVE CASH FLOW",
                "[AVOID] Property costs more than it earns every month.")
    _dscr = dscr if dscr is not None else 999
    if coc > 12 and _dscr >= 1.25:
        return ("EXCELLENT ",
                "[STRONG BUY] Outstanding returns, healthy debt coverage.")
    if coc > 8 and _dscr >= 1.0:
        return ("GOOD ",
                "[BUY] Solid cash flow and acceptable debt service.")
    if coc > 5:
        return ("FAIR ",
                "[HOLD / NEGOTIATE] Marginal returns — try to reduce price or improve rent.")
    return ("POOR ",
            "[AVOID / RENEGOTIATE] Returns too low for the risk and capital locked in.")


def format_investment_report(m: Dict[str, Any]) -> str:
    quality, recommendation = _quality_badge(m['coc_roi'], m['dscr'], m['monthly_cf'])
    dscr_str    = f"{m['dscr']:.2f}x" if m['dscr'] is not None else "N/A (no loan)"
    dscr_signal = _dscr_label(m['dscr'])
    payback_str = f"{m['payback_years']:.1f} yrs" if m['payback_years'] is not None else "Never (negative CF)"
    payback_sig = ('OK' if m['payback_years'] is not None and m['payback_years'] < 15 else 'NO')
    irr_str     = f"{m['irr'] * 100:.1f}%" if m['irr'] is not None else "N/A (no convergence)"

    # 1% rule verdict
    one_pct = m['one_pct_ratio']
    if one_pct >= 1.0:
        one_pct_verdict = f" Passes (ratio {one_pct:.2f}x)"
    elif one_pct >= 0.75:
        one_pct_verdict = f" Close (ratio {one_pct:.2f}x — negotiate rent up)"
    else:
        one_pct_verdict = f" Fails (ratio {one_pct:.2f}x — rent too low for price)"

    report = f"""
INVESTMENT ANALYSIS REPORT

---

CAPITAL STRUCTURE
- Purchase Price: {_rs(m['price'])}
- Down Payment ({m['down_pct']:.0f}%): {_rs(m['down_payment'])}
- Stamp Duty + Registration (~{m['closing_costs']/m['price']*100:.0f}%): {_rs(m['closing_costs'])}
- Total Cash Required: {_rs(m['total_invested'])}
- Home Loan: {_rs(m['loan_amount'])} @ {m['interest_rate']:.1f}% for {m['loan_term']} yrs

---

MONTHLY CASH FLOW
- Rental Income: +{_rs(m['monthly_rent'])}
- Operating Expenses ({m['expense_ratio']*100:.0f}%): -{_rs(m['monthly_opex'])}
- EMI: -{_rs(m['monthly_emi'])}
- CapEx Reserve: -{_rs(m['annual_capex']/12)}
- Net Monthly Cash Flow: {_rs(m['monthly_cf'])}** {"Fine" if m['monthly_cf'] >= 0 else "No"}

---

ANNUAL PERFORMANCE
- Gross Rental Income: {_rs(m['annual_rent'])}
- Operating Expenses: -{_rs(m['annual_opex'])}
- Net Operating Income (NOI): {_rs(m['annual_noi'])}
- Total Debt Service (EMI × 12): -{_rs(m['annual_debt'])}
- CapEx Reserve: -{_rs(m['annual_capex'])}
- Annual Cash Flow: {_rs(m['annual_cf'])}

---

KEY INVESTMENT METRICS

| Metric | Value | Signal |
|--------|-------|--------|
| Gross Yield | {_pct(m['gross_yield'])} | {'Good' if m['gross_yield'] > 4 else 'Low'} |
| Cap Rate (NOI/Price) | {_pct(m['cap_rate'])} | {'Good' if m['cap_rate'] > 3.5 else ' Low'} |
| Cash-on-Cash ROI | {_pct(m['coc_roi'])} | {'Excellent' if m['coc_roi'] > 10 else 'Good' if m['coc_roi'] > 6 else 'Fair' if m['coc_roi'] > 3 else 'Poor'} |
| DSCR | {dscr_str} | {dscr_signal} |
| Break-even Occupancy | {_pct(m['break_even_occ'])} | {'Safe' if m['break_even_occ'] < 80 else 'Risky'} |
| 1% Rule | {one_pct_verdict} | — |
| Payback Period | {payback_str} | {payback_sig} |

---

ADVANCED METRICS

- IRR ({m['holding_years']}-year horizon): {irr_str}
  (Accounts for annual cash flows + sale proceeds after {m['holding_years']} years)

- Appreciation Model ({m['appreciation_rate']:.1f}%/yr over {m['holding_years']} yrs):
  - Current Value:  {_rs(m['price'])}
  - Future Value:   {_rs(m['future_value'])}
  - Capital Gain:   {_rs(m['equity_gain'])}
  - Loan Outstanding at Exit: {_rs(m['loan_balance_exit'])}
  - Net Sale Proceeds: {_rs(m['net_sale_proceeds'])}

---

INVESTMENT QUALITY: {quality}

RECOMMENDATION:
{recommendation}

---

**INDIA-SPECIFIC NOTES**
- Stamp duty & registration vary by state (4–8%); 7% used here
- Home loan EMI may qualify for Section 80C + 24(b) deductions (up to Rs. 2L interest)
- Rental income taxable after 30% standard deduction on NAV
- TDS @ 31.2% for NRI landlords; 10% for residents if rent > Rs. 2.4L/yr
- Consider society maintenance, property tax (~0.5–1% of value), and vacancy buffer
"""
    return report.strip()


_analyzer = InvestmentAnalyzer()


class LocalExpertAgent:
   

    def __init__(self):
        self.name       = "GeoInsight AI Agent"
        self.use_gemini = GEMINI_AVAILABLE

    async def _gemini(self, prompt: str) -> Optional[str]:
        if not self.use_gemini:
            return None
        try:
            model    = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"[Gemini error] {e}")
            return None

    
    async def process_query(self, query: str) -> Dict[str, Any]:
        q = query.lower()
        nums = extract_labeled_numbers(query)

        is_investment_query = any(
            w in q for w in
            ['investment', 'roi', 'irr', 'calculate', 'analyze', 'analyse',
             'cash flow', 'yield', 'return', 'dscr', 'buy', 'mortgage', 'net cash']
        )

        annual_mortgage_match = re.search(
            r'annual\s+(?:mortgage|emi|loan)\s+(?:payments?\s+)?(?:total|is|=|:)?\s*'
            r'(?:Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?(?:\s*(?:L|Cr|K|lakh|crore))?)',
            q
        )
        if annual_mortgage_match and nums['price'] and nums['rent']:
            raw_amt = annual_mortgage_match.group(1).replace(',', '').strip()
        
            annual_emi = None
            for suf, mult in _SUFFIX.items():
                if raw_amt.lower().endswith(suf.lower()):
                    try:
                        annual_emi = float(raw_amt[:-(len(suf))]) * mult
                    except ValueError:
                        pass
                    break
            if annual_emi is None:
                try:
                    annual_emi = float(raw_amt)
                except ValueError:
                    annual_emi = None

            if annual_emi:
                expense_ratio = nums['expense_ratio'] or InvestmentAnalyzer.DEFAULT_EXPENSE_RATIO
                annual_rent   = nums['rent'] * 12
                annual_opex   = annual_rent * expense_ratio
                annual_noi    = annual_rent - annual_opex
                annual_capex  = nums['price'] * InvestmentAnalyzer.DEFAULT_CAPEX_RESERVE
                annual_cf     = annual_noi - annual_emi - annual_capex
                monthly_cf    = annual_cf / 12
                monthly_emi   = annual_emi / 12

                
                down_pct      = nums['down_pct'] or InvestmentAnalyzer.DEFAULT_DOWN_PCT
                down_payment  = nums['price'] * (down_pct / 100)
                closing       = nums['price'] * InvestmentAnalyzer.DEFAULT_CLOSING_COSTS
                total_invested = down_payment + closing

                coc_roi        = (annual_cf / total_invested * 100) if total_invested > 0 else 0
                cap_rate       = (annual_noi / nums['price'] * 100) if nums['price'] > 0 else 0
                gross_yield    = (annual_rent / nums['price'] * 100) if nums['price'] > 0 else 0
                dscr           = annual_noi / annual_emi if annual_emi > 0 else None
                monthly_opex   = annual_opex / 12
                beo            = ((monthly_emi + monthly_opex) / nums['rent'] * 100
                                  if nums['rent'] > 0 else 100.0)
                beo            = min(beo, 100.0)
                payback        = total_invested / annual_cf if annual_cf > 0 else None

                dscr_str    = f"{dscr:.2f}x" if dscr is not None else "N/A"
                payback_str = f"{payback:.1f} yrs" if payback is not None else "Never (negative CF)"

                answer = f"""INVESTMENT ANALYSIS — Custom Mortgage Input
(Annual mortgage provided directly: {_rs(annual_emi)}/yr = {_rs(monthly_emi)}/month)

---

MONTHLY CASH FLOW
- Rental Income: +{_rs(nums['rent'])}
- Operating Expenses ({expense_ratio*100:.0f}%): -{_rs(monthly_opex)}
- EMI: -{_rs(monthly_emi)}
- CapEx Reserve: -{_rs(annual_capex/12)}
- Net Monthly Cash Flow: {_rs(monthly_cf)} {"✅" if monthly_cf >= 0 else "❌"}

---

ANNUAL PERFORMANCE
- Gross Rent: {_rs(annual_rent)}
- Operating Expenses: -{_rs(annual_opex)}
- NOI: {_rs(annual_noi)}
- Debt Service: -{_rs(annual_emi)}
- CapEx Reserve: -{_rs(annual_capex)}
- Annual Cash Flow: {_rs(annual_cf)}

---

KEY METRICS
| Metric | Value |
|--------|-------|
| Gross Yield | {_pct(gross_yield)} |
| Cap Rate | {_pct(cap_rate)} |
| Cash-on-Cash ROI | {_pct(coc_roi)} |
| DSCR | {dscr_str} |
| Break-even Occupancy | {_pct(beo)} |
| Payback Period | {payback_str} |

Note: Cash-on-Cash ROI estimated using {down_pct:.0f}% down + 7% closing costs = {_rs(total_invested)} total invested.
Provide down payment % for a more precise figure.
"""
                return _safe({
                    'query': query,
                    'answer': answer,
                    'calculations': {
                        'price': nums['price'], 'monthly_rent': nums['rent'],
                        'monthly_cf': monthly_cf, 'annual_cf': annual_cf,
                        'coc_roi': coc_roi, 'cap_rate': cap_rate,
                        'gross_yield': gross_yield, 'dscr': dscr,
                        'break_even_occ': beo, 'payback_years': payback,
                        'annual_noi': annual_noi,
                    },
                    'success': True, 'confidence': 0.93,
                    'type': 'investment_analysis',
                })
        if is_investment_query and nums['price'] and nums['rent']:
            kwargs: Dict[str, Any] = {}
            if nums['down_pct'] is not None:
                kwargs['down_pct']          = nums['down_pct']
            if nums['interest_rate'] is not None:
                kwargs['interest_rate']     = nums['interest_rate']
            if nums['loan_term'] is not None:
                kwargs['loan_term']         = int(nums['loan_term'])
            if nums['expense_ratio'] is not None:
                kwargs['expense_ratio']     = nums['expense_ratio']
            if nums['holding_years'] is not None:
                kwargs['holding_years']     = int(nums['holding_years'])
            if nums['appreciation_rate'] is not None:
                kwargs['appreciation_rate'] = nums['appreciation_rate']

            metrics = _analyzer.compute(nums['price'], nums['rent'], kwargs)
            report  = format_investment_report(metrics)

            return _safe({
                'query':       query,
                'answer':      report,
                'calculations': metrics,
                'success':     True,
                'confidence':  0.97,
                'type':        'investment_analysis',
            })

       
        if any(w in q for w in ['price', 'worth', 'value', 'cost', 'rate per sqft']):
            if nums['price']:
                price = nums['price']

              
                if self.use_gemini:
                    g = await self._gemini(
                        f"You are an Indian real estate advisor (Mumbai / Bangalore / Delhi markets). "
                        f"A user asks: {query}. "
                        f"Provide brief, practical advice in Rs. (use Lakhs/Crores). "
                        f"Mention segment (affordable/mid/luxury), typical ₹/sqft, and 2-sentence verdict."
                    )
                    if g:
                        return {'query': query, 'answer': g, 'success': True,
                                'confidence': 0.90, 'source': 'gemini', 'type': 'price_analysis'}

                # Fallback
                if price >= 1_00_00_000:
                    segment, sqft_range = "Luxury / Premium",     "Rs. 10,000–25,000/sqft"
                elif price >= 50_00_000:
                    segment, sqft_range = "Mid-segment",          "Rs. 5,000–10,000/sqft"
                else:
                    segment, sqft_range = "Affordable / Entry",   "Rs. 3,000–5,000/sqft"

                answer = f"""PRICE ANALYSIS — India Market

Property Value: {_rs(price)}

Market Segment: {segment}
Typical Rate: {sqft_range}

Approximate Size at This Price:
- Economy location: ~{int(price/4000):,} sqft
- Mid-city location: ~{int(price/7000):,} sqft
- Prime location:   ~{int(price/12000):,} sqft

Quick Sanity Checks:
- Fair rental yield (India): 2–4% gross
- Minimum monthly rent for viability: {_rs(price * 0.003)} – {_rs(price * 0.004)}

Recommendation: Get 3 comparable sales (comps) from the same micro-market
to validate. Use PropTiger, 99acres, or MagicBricks for local benchmarks."""

                return {'query': query, 'answer': answer, 'success': True,
                        'confidence': 0.80, 'type': 'price_analysis'}

       
        if any(w in q for w in ['rent', 'rental', 'lease', 'monthly income']):
            if nums['rent']:
                rent = nums['rent']
                implied_value = rent * (12 / 0.03) 

                answer = f"""RENTAL MARKET ANALYSIS — India

Monthly Rent: {_rs(rent)}

Implied Property Value (at 3% gross yield): {_rs(implied_value)}
Acceptable range: {_rs(implied_value * 0.8)} – {_rs(implied_value * 1.2)}

Landlord Economics (30% expense ratio):
- Operating expenses: {_rs(rent * 0.30)}/month
- Net income after expenses: {_rs(rent * 0.70)}/month
- Target gross yield: 3–5% (India metros)

Tenant Affordability:
- Rule of thumb: Rent ≤ 30% of take-home pay
- Minimum household income needed: {_rs(rent * 3.5)}/month ({_rs(rent * 42)}/year)

Market Benchmarks (India 2024):
- Studio / 1BHK (Metro): Rs. 15,000 – 35,000/month
- 2BHK (Metro):          Rs. 25,000 – 65,000/month
- 3BHK (Metro):          Rs. 40,000 – 1.2L/month

Verdict: {"Market-rate" if 15000 <= rent <= 150000 else " Verify against local comparables"}"""

                return {'query': query, 'answer': answer, 'success': True,
                        'confidence': 0.85, 'type': 'rental_analysis'}

        if self.use_gemini:
            g = await self._gemini(
                f"You are a professional Indian real estate advisor. "
                f"Answer concisely and practically. Use Rs. (Lakhs/Crores). "
                f"User question: {query}"
            )
            if g:
                return {'query': query, 'answer': g, 'success': True,
                        'confidence': 0.88, 'source': 'gemini', 'type': 'general'}

        return {
            'query': query,
            'answer': """GeoInsight AI — India Real Estate Assistant**

I can help you with:

Investment Analysis (full metrics: IRR, DSCR, CoC ROI, break-even):
- "Analyze investment: property Rs. 80L, rent Rs. 25,000/month"
- "ROI for 1.2 Cr flat with 40,000 monthly rent, 20% down, 8.5% interest"
- "Calculate IRR for 50L property, 18000 rent, hold 10 years, 5% appreciation"

Price Analysis:
- "Is Rs. 90L a good price for a 2BHK in Bangalore?"
- "What is fair value for a property at Rs. 7,500/sqft in Pune?"

Rental Analysis:
- "Fair rent for a 75L flat in Mumbai?"
- "Expected rent for Rs. 1.5 Cr property in Delhi NCR?"

Tip: You can specify expense ratio, interest rate, holding period, and appreciation
rate to get a fully customised analysis.""",
            'success': True,
            'confidence': 0.70,
            'type': 'help',
        }

agent = LocalExpertAgent()