import streamlit as st
from api_client import api
from utils import (
    format_currency, format_number, format_percentage,
    get_roi_label, show_success_message, show_error_message,
    get_session_state, set_session_state
)
from components.header import render_section_header
from datetime import datetime

def render_ai_assistant_page():
    render_section_header("AI Real Estate Assistant")
    
    st.markdown("Ask anything about a property — valuations, rental potential, investment returns, and more.")
    
    render_example_queries()
    render_query_interface()

    if st.session_state.get('show_ai_history', False):
        st.divider()
        render_query_history()

def render_example_queries():
    with st.expander("Try asking"):
        st.markdown("""
        Investment Analysis:
        - Analyse investment: property Rs. 80L, rent Rs. 25,000/month
        - ROI for 1.2 Cr flat with 40,000 monthly rent, 20% down
        
        Property Valuation:
        - Is Rs. 90L a good price for a 2BHK in Bangalore?
        - Fair value for a property at Rs. 7,500/sqft in Pune?
        
        Rental Analysis:
        - Fair rent for a 75L flat in Mumbai?
        - Expected rent for Rs. 1.5 Cr property in Delhi NCR?
        """)

def render_query_interface():
    # Use a counter to force widget re-creation on clear
    if 'ai_clear_counter' not in st.session_state:
        st.session_state['ai_clear_counter'] = 0

    default_query = get_session_state('ai_query', '')

    query = st.text_area(
        "Ask Your Question",
        value=default_query,
        placeholder="e.g., Calculate ROI for Rs. 80L property with Rs. 25,000 monthly rent",
        height=100,
        key=f"ai_assistant_query_{st.session_state['ai_clear_counter']}"
    )
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        ask_button = st.button(
            "Ask AI Assistant", 
            type="primary", 
            use_container_width=True,
            key="ask_ai"
        )
    
    with col2:
        if st.button("Clear", use_container_width=True, key="clear_ai"):
            # Clear query text by incrementing counter (forces new widget key)
            set_session_state('ai_query', '')
            st.session_state['ai_clear_counter'] += 1
            st.rerun()
    
    with col3:
        show_hist = st.session_state.get('show_ai_history', False)
        label = "Hide History" if show_hist else "History"
        if st.button(label, use_container_width=True, key="toggle_history"):
            st.session_state['show_ai_history'] = not show_hist
            st.rerun()
    
    if ask_button and query and query.strip():
        # Save the current query to session state so it persists
        set_session_state('ai_query', query)
        handle_query_submission(query)
    elif ask_button:
        show_error_message("Please enter a question")

def handle_query_submission(query: str):
    with st.spinner("Analysing..."):
        response = api.query_ai_agent(query)
    
    if not response:
        return
    
    if not response.get('success'):
        show_error_message("AI query failed")
        return
    
    history = get_session_state('agent_history', [])
    history.append({
        'query': query,
        'response': response,
        'timestamp': datetime.now()
    })
    st.session_state.agent_history = history[-20:]
    
    render_ai_response(response)

def render_ai_response(response: dict):
    st.markdown("### Response")
    
    answer = response.get('response', {}).get('answer', '')
    st.markdown(answer)
    
    calculations = response.get('response', {}).get('calculations')
    if calculations:
        render_investment_breakdown(calculations)
    
    confidence = response.get('confidence', 0)
    if confidence:
        render_confidence_score(confidence)

def render_investment_breakdown(calculations: dict):
    st.divider()
    st.subheader("Investment Breakdown")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        price = calculations.get('price', 0)
        st.metric("Price", format_currency(price))
    
    with col2:
        rent = calculations.get('monthly_rent', 0)
        st.metric("Rent/Mo", format_currency(rent))
    
    with col3:
        cash_flow = calculations.get('monthly_cf', calculations.get('monthly_cash_flow', 0))
        st.metric("Cash Flow", format_currency(cash_flow))
    
    with col4:
        roi = calculations.get('coc_roi', calculations.get('cash_on_cash_roi', 0))
        label = get_roi_label(roi)
        st.metric("ROI", f"{roi:.1f}%", help=str(label))
    
    with st.expander("Full Financial Details"):
        render_financial_details(calculations)

def render_financial_details(calc: dict):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Investment**")
        st.write(f"Down Payment: {format_currency(calc.get('down_payment', 0))}")
        st.write(f"Down %: {calc.get('down_pct', calc.get('down_payment_pct', 0)):.0f}%")
        st.write(f"Loan Amount: {format_currency(calc.get('loan_amount', 0))}")
        st.write(f"Interest Rate: {calc.get('interest_rate', 0):.1f}%")
    
    with col2:
        st.markdown("**Monthly**")
        st.write(f"EMI: {format_currency(calc.get('monthly_emi', calc.get('monthly_mortgage', 0)))}")
        st.write(f"Expenses: {format_currency(calc.get('monthly_opex', calc.get('monthly_expenses', 0)))}")
        st.write(f"Net Cash Flow: {format_currency(calc.get('monthly_cf', calc.get('monthly_cash_flow', 0)))}")
    
    st.markdown("**Annual**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"Gross Rent: {format_currency(calc.get('annual_rent', 0))}")
    with col2:
        st.write(f"Expenses: {format_currency(calc.get('annual_opex', calc.get('annual_expenses', 0)))}")
    with col3:
        st.write(f"NOI: {format_currency(calc.get('annual_noi', calc.get('annual_net_income', 0)))}")
    
    st.markdown("**Key Ratios**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"Gross Yield: {format_percentage(calc.get('gross_yield', calc.get('rental_yield', 0)))}")
    with col2:
        st.write(f"Cap Rate: {format_percentage(calc.get('cap_rate', 0))}")
    with col3:
        st.write(f"Break-Even: {format_percentage(calc.get('break_even_occ', calc.get('break_even_occupancy', 0)))}")

def render_confidence_score(confidence: float):
    st.divider()
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.progress(confidence)
    with col2:
        st.metric("Reliability", format_percentage(confidence * 100, decimals=0))

def render_query_history():
    st.subheader("Query History")
    
    history = get_session_state('agent_history', [])
    
    if not history:
        st.info("No query history yet. Ask a question to get started!")
        return
    
    for idx, item in enumerate(reversed(history)):
        render_history_item(item, idx)

def render_history_item(item: dict, idx: int):
    query = item['query']
    timestamp = item['timestamp'].strftime('%Y-%m-%d %H:%M')
    
    with st.expander(f"{query[:60]}{'...' if len(query) > 60 else ''}"):
        st.caption(f"Asked: {timestamp}")
        
        response = item['response']
        answer = response.get('response', {}).get('answer', '')
        
        if len(answer) > 300:
            st.markdown(answer[:300] + '...')
            if st.button("Show Full", key=f"expand_{idx}"):
                st.markdown(answer)
        else:
            st.markdown(answer)
        
        calc = response.get('response', {}).get('calculations')
        if calc:
            col1, col2, col3 = st.columns(3)
            with col1:
                roi = calc.get('coc_roi', calc.get('cash_on_cash_roi', 0))
                st.metric("ROI", f"{roi:.1f}%")
            with col2:
                flow = calc.get('monthly_cf', calc.get('monthly_cash_flow', 0))
                st.metric("Cash Flow", format_currency(flow))
            with col3:
                price = calc.get('price', 0)
                st.metric("Price", format_currency(price))
        
        if st.button("Ask Again", key=f"reuse_{idx}", use_container_width=True):
            set_session_state('ai_query', query)
            st.rerun()