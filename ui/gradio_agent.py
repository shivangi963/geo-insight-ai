import gradio as gr
import requests
import json
import sys

# FastAPI URL
API_URL = "http://localhost:8000"

def query_agent(user_query):
    """
    Send query to agent API
    """
    try:
        response = requests.post(
            f"{API_URL}/api/agent/query",
            json={"query": user_query},
            timeout=30
        )
        
        print(f"DEBUG: Status Code: {response.status_code}")  # Debug print
        
        if response.status_code == 200:
            result = response.json()
            print(f"DEBUG: Response keys: {list(result.keys())}")  # Debug print
            
            # Format the response
            formatted = f"**Query:** {user_query}\n\n"
            
            if result.get('tool_used'):
                formatted += f"**Tool Used:** {result['tool_used']}\n\n"
                
                # Show tool result in expandable section
                tool_result = json.dumps(result.get('tool_result', {}), indent=2)
                formatted += f"<details><summary>📊 Tool Result</summary>\n```json\n{tool_result}\n```\n</details>\n\n"
            
            # Always include the answer if it exists
            if 'answer' in result:
                formatted += f"**Answer:**\n{result['answer']}"
            else:
                formatted += f"**Response:**\n{json.dumps(result, indent=2)}"
            
            return formatted
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Connection error: {str(e)}"

# Create interface
iface = gr.Interface(
    fn=query_agent,
    inputs=gr.Textbox(
        label="Ask a question",
        placeholder="E.g., 'Calculate ROI for a $300k property with $2000 monthly rent' or 'Is $450,000 a good price?'",
        lines=3
    ),
    outputs=gr.Markdown(label="Agent Response"),
    title="🤖 GeoInsight AI - Local Expert Agent",
    description="Ask questions about real estate, investments, or neighborhoods. The AI agent will analyze and provide insights.",
    examples=[
        "Calculate ROI for $300k property with $2000 rent",
        "Is $450,000 a good price for a house?",
        "What can I get for $1500 monthly rent?",
        "Investment analysis: $500k house, $3000 rent, 20% down",
        "Price check: $750,000 property"
    ]
)

if __name__ == "__main__":
    print("🚀 Starting GeoInsight AI Agent Interface...")
    print(f"🌐 Connecting to API at: {API_URL}")
    print(f"🔗 Local URL: http://localhost:7861")
    print(f"🔗 Alternative URL: http://127.0.0.1:7861")
    
    # Try different ports if 7861 doesn't work
    ports_to_try = [7861, 7862, 8888, 8080]
    
    for port in ports_to_try:
        try:
            print(f"\n🔧 Trying port {port}...")
            iface.launch(
                server_name="127.0.0.1",  # Use 127.0.0.1
                server_port=port,
                share=False,
                debug=False
            )
            break  # If successful, stop trying ports
        except Exception as e:
            print(f"❌ Port {port} failed: {str(e)[:100]}")
            if port == ports_to_try[-1]:
                print("⚠️ All ports failed. Trying with share=True...")
                iface.launch(share=True)  # Last resort: use Gradio's public link