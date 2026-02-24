Project Vision — GeoInsight AI

 The Problem

Finding the right place to rent, invest, or open a business is really hard. Information is scattered everywhere — rental websites, government demographic data, Google Maps, satellite images — and none of it talks to each other. Most people end up making expensive decisions based on gut feeling or incomplete data.

I've personally seen this problem in my own city. Landlords don't know if their rent is fair. Small business owners pick locations that fail because they didn't know foot traffic or nearby competition. Investors buy properties without understanding the actual neighborhood quality.

---

 What GeoInsight AI Does

GeoInsight AI brings everything together into one intelligent platform. You type in an address and ask a question like *"Is this a good area to open a cafe?"* — and the system goes to work.

It pulls data from OpenStreetMap to find nearby amenities, runs computer vision on street-level imagery to detect things like cars, greenery, and infrastructure quality, uses AI language models to synthesize all of it into a plain-English report, and cross-references real financial data to estimate rental returns and investment potential.

The goal is to replace hours of manual research with a 30-second AI-powered answer.

---

 Who Is This For?

- Rental investors who want to evaluate a property before buying
- Small business owners deciding where to open a shop or restaurant
- City planners who need quick data about neighborhood quality
- Renters who want to understand an area before signing a lease

---

 Why AI / ML Is the Right Tool

Traditional tools show you a map or a table of data. AI can *reason* about that data. A language model can look at the combination of "3 hospitals nearby, low walk score, high green space, average rent Rs. 25,000/month" and actually tell you what that means for your use case. Computer vision can look at a satellite image and quantify how much of the neighborhood is green space — something that would take a human analyst hours to measure.

The combination of geospatial data + computer vision + LLMs is what makes this genuinely useful rather than just another dashboard.

---

 Technical Approach

The system is built in layers:

1. Data layer — MongoDB stores property data and analysis results. Supabase (with pgvector) stores image embeddings for visual similarity search.
2. Processing layer — FastAPI backend orchestrates everything. Celery + Redis handle long-running tasks asynchronously.
3. AI layer — YOLOv8 for object detection and green space analysis. CLIP for image embeddings. Gemini API for the intelligent agent that synthesizes everything.
4. Workflow layer — n8n orchestrates the full analysis pipeline and sends email notifications when results are ready.
5. Frontend — Streamlit dashboard that non-technical users can actually use.

---

 What Success Looks Like

A user enters an address, asks a question, and gets back a structured report within 2-3 minutes that includes:
- Walk score and nearby amenities map
- Green space percentage from satellite imagery
- Investment analysis with IRR, DSCR, cash-on-cash ROI
- Visually similar properties from the vector database
- A plain-English recommendation

That's the vision. Everything in this project is built toward making that moment possible.