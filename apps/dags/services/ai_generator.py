import json
import re
from django.conf import settings
from openai import OpenAI


def generate_mock_dag(prompt: str) -> dict:
    """
    Local rule-based generator that converts a plain English prompt into a sequential
    DAG pipeline. Used as a fallback when no valid OpenAI API key is provided.
    """
    # Split prompt by common separators: comma, semicolon, "then", "and then", "next", "after that"
    parts = re.split(r',|;|(?:\band\s+)?\bthen\b|(?:\band\s+)?\bnext\b|\bafter\s+that\b', prompt, flags=re.IGNORECASE)
    
    tasks = []
    dependencies = []
    prev_task_name = None
    
    for part in parts:
        part = part.strip()
        # Clean up common starting words
        part = re.sub(r'^(?:and|to|first|firstly|finally|lastly|then|next)\s+', '', part, flags=re.IGNORECASE).strip()
        if not part or len(part) < 3:
            continue
            
        # Clean name for the node
        clean_name = part.replace('"', '').replace("'", "").strip()
        # Capitalize first letter of every word for cleaner labels
        clean_name = clean_name.title()
        if len(clean_name) > 35:
            clean_name = clean_name[:32] + '...'
            
        # Avoid duplicate task names
        if any(t['name'] == clean_name for t in tasks):
            continue
            
        tasks.append({
            "name": clean_name,
            "description": f"Step: {part}",
            "task_type": "DUMMY",
            "task_config": {"duration": 3}
        })
        
        if prev_task_name:
            dependencies.append({
                "task": clean_name,
                "depends_on": prev_task_name
            })
            
        prev_task_name = clean_name

    # Default fallback if no tasks were parsed
    if not tasks:
        tasks = [
            {"name": "Extract Raw Data", "description": "Fetch raw data from input sources", "task_type": "DUMMY", "task_config": {"duration": 3}},
            {"name": "Transform & Clean Data", "description": "Perform data cleansing and transformations", "task_type": "DUMMY", "task_config": {"duration": 3}},
            {"name": "Load Into DB", "description": "Save the processed results to database", "task_type": "DUMMY", "task_config": {"duration": 3}}
        ]
        dependencies = [
            {"task": "Transform & Clean Data", "depends_on": "Extract Raw Data"},
            {"task": "Load Into DB", "depends_on": "Transform & Clean Data"}
        ]
        
    return {
        "tasks": tasks,
        "dependencies": dependencies
    }


def generate_gemini_dag(prompt: str, api_key: str) -> dict:
    """
    Uses Google's free-tier Gemini API (tries 2.5 Flash, falls back to 1.5 Flash)
    to convert a plain English pipeline description into a structured DAG definition.
    """
    import urllib.request
    import urllib.error
    import json
    
    candidates = [
        ("v1", "gemini-2.5-flash"),
        ("v1beta", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-flash"),
    ]
    
    system_instruction = """You are a workflow pipeline designer. 
    Convert the user's plain English description into a structured DAG (Directed Acyclic Graph) pipeline.
    
    Return ONLY valid JSON with this exact structure:
    {
        "tasks": [
            {
                "name": "Task Name",
                "description": "What this task does",
                "task_type": "DUMMY",
                "task_config": {"duration": 3}
            }
        ],
        "dependencies": [
            {
                "task": "Task B Name",
                "depends_on": "Task A Name"
            }
        ]
    }
    
    Rules:
    - task_type should always be "DUMMY" unless the user specifies HTTP or Python
    - task names should be short and descriptive (3-5 words max)
    - dependencies define which tasks must complete before another can start
    - Identify which tasks can run in parallel (no dependency between them)
    - Return ONLY the JSON, no explanation, no markdown wrapping.
    """
    
    headers = {"Content-Type": "application/json"}
    last_err = None
    
    for api_version, model_name in candidates:
        url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent?key={api_key}"
        
        # Try both with and without responseMimeType for maximum key and version compatibility
        payload_options = [
            {
                "contents": [{"parts": [{"text": f"{system_instruction}\n\nCreate a pipeline for: {prompt}"}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.3
                }
            },
            {
                "contents": [{"parts": [{"text": f"{system_instruction}\n\nCreate a pipeline for: {prompt}"}]}],
                "generationConfig": {
                    "temperature": 0.3
                }
            }
        ]
        
        for payload in payload_options:
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    # If JSON response has markdown code blocks, strip them
                    clean_json = content_text.strip()
                    if clean_json.startswith("```"):
                        # remove ```json and ``` wrapping if present
                        clean_json = re.sub(r'^```(?:json)?\n|```$', '', clean_json, flags=re.IGNORECASE).strip()
                    return json.loads(clean_json)
            except Exception as e:
                last_err = e
                continue
            
    if last_err:
        raise last_err
    raise Exception("Failed to generate DAG with all Gemini model candidates")


def generate_dag_from_prompt(prompt: str) -> dict:
    """
    Generates a structured DAG from a plain English prompt.
    Prioritizes Google Gemini API (great free tier), falls back to OpenAI,
    and ultimately falls back to the local rule-based mock parser.
    """
    import os
    gemini_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    openai_key = getattr(settings, 'OPENAI_API_KEY', '') or os.getenv('OPENAI_API_KEY', '')

    # 1. Prioritize Google Gemini (completely free tier)
    if gemini_key and gemini_key.strip() != "" and "your-gemini-api-key" not in gemini_key:
        try:
            return generate_gemini_dag(prompt, gemini_key)
        except Exception:
            pass # Fall back to OpenAI or Mock if Gemini fails

    # 2. Fall back to OpenAI
    if openai_key and openai_key.strip() != "" and "your-openai-api-key" not in openai_key:
        try:
            client = OpenAI(api_key=openai_key)
            system_prompt = """You are a workflow pipeline designer. 
            Convert the user's plain English description into a structured DAG (Directed Acyclic Graph) pipeline.
            
            Return ONLY valid JSON with this exact structure:
            {
                "tasks": [
                    {
                        "name": "Task Name",
                        "description": "What this task does",
                        "task_type": "DUMMY",
                        "task_config": {"duration": 3}
                    }
                ],
                "dependencies": [
                    {
                        "task": "Task B Name",
                        "depends_on": "Task A Name"
                    }
                ]
            }
            
            Rules:
            - task_type should always be "DUMMY" unless the user specifies HTTP or Python
            - task names should be short and descriptive (3-5 words max)
            - dependencies define which tasks must complete before another can start
            - Identify which tasks can run in parallel (no dependency between them)
            - Return ONLY the JSON, no explanation
            """

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a pipeline for: {prompt}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            return json.loads(response.choices[0].message.content)
        except Exception:
            pass # Fall back to Mock if OpenAI fails

    # 3. Ultimate local fallback
    return generate_mock_dag(prompt)

