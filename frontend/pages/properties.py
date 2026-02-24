import streamlit as st
import pandas as pd
import plotly.express as px
from api_client import api
from utils import (
    format_currency, format_number, calculate_price_per_sqft,
    show_success_message, show_error_message, init_session_state
)
from components.header import render_section_header

def safe_filter_properties(properties, city_filter, type_filter, bedrooms_filter):
    filtered = properties

    if city_filter != "All" and city_filter:
        filtered = [
            p for p in filtered
            if str(p.get('city', '')).strip().lower() == str(city_filter).strip().lower()
        ]

    if type_filter != "All" and type_filter:
        filtered = [
            p for p in filtered
            if str(p.get('property_type', '')).strip().lower() == str(type_filter).strip().lower()
        ]

    if bedrooms_filter != "All" and bedrooms_filter:
        try:
            bed_value = int(bedrooms_filter)
            filtered = [
                p for p in filtered
                if int(p.get('bedrooms', 0)) == bed_value
            ]
        except (ValueError, TypeError):
            filtered = [
                p for p in filtered
                if str(p.get('bedrooms', '')).strip() == str(bedrooms_filter).strip()
            ]

    return filtered


def render_properties_page():
    render_section_header("Properties")

    browse_tab, compare_tab, add_tab = st.tabs([
        " Browse",
        " Compare",
        " Add Property"
    ])

    with browse_tab:
        render_browse_properties()

    with compare_tab:
        render_compare_properties()

    with add_tab:
        render_add_property()


def render_browse_properties():
    col1, col2 = st.columns([3, 1])

    with col2:
        if st.button("Refresh", use_container_width=True, key="refresh_props"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Loading properties..."):
        properties = api.get_properties(limit=100)

    if not properties or len(properties) == 0:
        st.info("No properties in database")
        render_no_properties_help()
        return

    df = pd.DataFrame(properties)

    render_property_metrics(df)

    st.divider()

    filtered_df = render_property_filters(df)

    st.success(f"Showing {len(filtered_df)} properties")

    render_property_list(filtered_df)


def render_property_metrics(df: pd.DataFrame):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(" Total", len(df))

    with col2:
        if 'price' in df.columns:
            avg_price = df['price'].mean()
            st.metric("Avg Price", format_currency(avg_price))

    with col3:
        if 'square_feet' in df.columns:
            avg_sqft = df['square_feet'].mean()
            st.metric(" Avg Size", f"{avg_sqft:,.0f} sqft")

    with col4:
        if 'city' in df.columns:
            unique_cities = df['city'].nunique()
            st.metric("Cities", unique_cities)


def render_property_filters(df: pd.DataFrame) -> pd.DataFrame:
    col1, col2, col3 = st.columns(3)

    properties = df.to_dict('records')

    with col1:
        if 'city' in df.columns:
            cities = list(set([str(p.get('city', 'Unknown')).strip() for p in properties if p.get('city')]))
            cities.sort()
            city_filter = st.selectbox("City", ["All"] + cities, key="city_filter")
        else:
            city_filter = "All"

    with col2:
        if 'property_type' in df.columns:
            types = list(set([str(p.get('property_type', 'Unknown')).strip() for p in properties if p.get('property_type')]))
            types.sort()
            type_filter = st.selectbox("Type", ["All"] + types, key="type_filter")
        else:
            type_filter = "All"

    with col3:
        if 'bedrooms' in df.columns:
            bedrooms = list(set([str(p.get('bedrooms', '0')).strip() for p in properties if p.get('bedrooms')]))
            bedrooms.sort(key=lambda x: int(x) if x.isdigit() else 0)
            bedrooms_filter = st.selectbox("Bedrooms", ["All"] + bedrooms, key="bed_filter")
        else:
            bedrooms_filter = "All"

    filtered_properties = safe_filter_properties(properties, city_filter, type_filter, bedrooms_filter)

    filtered_df = pd.DataFrame(filtered_properties) if filtered_properties else pd.DataFrame()

    if 'price' in df.columns and len(df) > 0 and len(filtered_df) > 0:
        min_p = int(df['price'].min())
        max_p = int(df['price'].max())
        if min_p < max_p:
            price_range = st.slider(
                "Price Range",
                min_p, max_p, (min_p, max_p),
                key="price_range"
            )
            filtered_df = filtered_df[
                (filtered_df['price'] >= price_range[0]) &
                (filtered_df['price'] <= price_range[1])
            ]

    return filtered_df


def render_property_list(df: pd.DataFrame):
    for idx, row in df.iterrows():
        render_property_card(row, idx)


def render_property_card(row: pd.Series, idx: int):
    price = row.get('price', 0)
    address = row.get('address', 'N/A')

    with st.expander(f"{address} | {format_currency(price)}", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("Location")
            st.write(f"{row.get('city', 'N/A')}, {row.get('state', 'N/A')}")
            st.write(f"ZIP: {row.get('zip_code', 'N/A')}")

        with col2:
            st.markdown("Details")
            st.write(f"Type: {row.get('property_type', 'N/A')}")
            beds = row.get('bedrooms', 'N/A')
            baths = row.get('bathrooms', 'N/A')
            st.write(f"Beds: {beds} | Baths: {baths}")

        with col3:
            st.markdown("Metrics")
            sqft = row.get('square_feet', 0)
            st.write(f"Size: {sqft:,} sqft")
            price_per_sqft = calculate_price_per_sqft(price, sqft)
            st.write(f"$/sqft: {format_currency(price_per_sqft)}")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("Analyze", key=f"analyze_{idx}"):
                st.session_state.nav_to_analysis = address
                show_success_message("Switched to Analysis tab")

        with col2:
            if st.button("AI Analysis", key=f"ai_{idx}"):
                query = f"Investment analysis for ${price:,.0f} property at {address}"
                st.session_state.ai_query = query
                show_success_message("Switched to AI tab")

def render_add_property():
    st.subheader(" Add New Property")

    with st.form("add_property_form"):
        col1, col2 = st.columns(2)

        with col1:
            address = st.text_input("Address *", placeholder="123 Main Street")
            city = st.text_input("City *", placeholder="Mumbai")
            state = st.text_input("tate *", placeholder="Maharashtra")
            zip_code = st.text_input("ZIP Code *", placeholder="400001")

        with col2:
            price = st.number_input("Price *", min_value=0, value=5000000, step=100000)
            bedrooms = st.number_input("Bedrooms *", min_value=0, value=2, step=1)
            bathrooms = st.number_input("Bathrooms *", min_value=0.0, value=2.0, step=0.5)
            square_feet = st.number_input("Square Feet *", min_value=0, value=1000, step=50)

        property_type = st.selectbox(
            " Property Type *",
            ["Apartment", "Villa", "Studio", "Penthouse", "Single Family",
             "Condo", "Townhouse", "Multi-Family"]
        )

        image_url = st.text_input(
            " Property Image URL",
            placeholder="https://images.unsplash.com/photo-xxx",
            help="Optional — add a photo URL to enable visual search for this property"
        )

        if image_url:
            try:
                st.image(image_url, caption="Preview", width=300)
                st.caption("This property will appear in photo-based searches")
            except:
                st.caption("Could not preview image — check the URL")

        submitted = st.form_submit_button(
            "Add Property",
            type="primary",
            use_container_width=True
        )

        if submitted:
            handle_property_submission(
                address, city, state, zip_code, price, bedrooms,
                bathrooms, square_feet, property_type, image_url
            )


def render_compare_properties():
    st.markdown("Select up to 3 properties to compare side by side.")

    properties = api.get_properties(limit=200)
    if not properties:
        st.info("No properties available.")
        return

    options = {
        f"{p.get('address', 'N/A')} — {p.get('price', 0):,.0f}": p
        for p in properties
    }

    selected_labels = st.multiselect(
        "Choose properties",
        list(options.keys()),
        max_selections=3,
        placeholder="Search by address…"
    )

    if len(selected_labels) < 2:
        st.info("Select at least 2 properties to compare.")
        return

    selected = [options[l] for l in selected_labels]

    cols = st.columns(len(selected))
    for col, prop in zip(cols, selected):
        with col:
            st.markdown(f"### {prop.get('address','')[:30]}")
            if prop.get("image_url"):
                st.image(prop["image_url"], use_container_width=True)

    st.divider()

    fields = [
        (" Price", "price", lambda v: f"{v:,.0f}"),
        (" Bedrooms", "bedrooms", lambda v: str(v)),
        (" Bathrooms", "bathrooms", lambda v: str(v)),
        (" Size (sqft)", "square_feet", lambda v: f"{v:,}"),
        (" Type", "property_type", lambda v: str(v)),
        (" City", "city", lambda v: str(v)),
    ]

    for label, key, fmt in fields:
        cols = st.columns(len(selected) + 1)
        with cols[0]:
            st.markdown(f"**{label}**")
        for col, prop in zip(cols[1:], selected):
            val = prop.get(key)
            with col:
                st.write(fmt(val) if val is not None else "—")

    st.divider()
    st.markdown("#### Price per sq.ft")
    chart_data = []
    for prop in selected:
        price = prop.get("price", 0)
        sqft = prop.get("square_feet", 1) or 1
        chart_data.append({
            "Property": prop.get("address","")[:25],
            "Price/sqft": round(price / sqft)
        })

    fig = px.bar(
        chart_data, x="Property", y="Price/sqft",
        color="Property",
        color_discrete_sequence=["#2563EB","#7C3AED","#059669"],
    )
    fig.update_layout(showlegend=False, height=300, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)


def handle_property_submission(address, city, state, zip_code, price,
                                bedrooms, bathrooms, square_feet,
                                property_type, image_url):
    if not all([address, city, state, zip_code]):
        show_error_message("Please fill all required fields (*)")
        return

    with st.spinner("Adding property..."):
        data = {
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "price": float(price),
            "bedrooms": int(bedrooms),
            "bathrooms": float(bathrooms),
            "square_feet": int(square_feet),
            "property_type": property_type,
            "image_url": image_url if image_url else None,
        }

        result = api.create_property(data)

        if result:
            if image_url:
                show_success_message(
                    "Property added! Visual similarity search enabled automatically "
                )
            else:
                show_success_message("Property added successfully!")


def render_no_properties_help():
    st.info("No properties have been added yet. Use the 'Add Property' tab to get started.")