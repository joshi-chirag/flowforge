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


def generate_dag_from_prompt(prompt: str) -> dict:
    """
    Uses OpenAI to convert a plain English pipeline description
    into a structured DAG definition. Falls back to generate_mock_dag if
    OpenAI API key is missing or invalid.
    """
    # Check if key is empty or default placeholder
    key = settings.OPENAI_API_KEY or ""
    if not key or "your-openai-api-key" in key or key.strip() == "":
        return generate_mock_dag(prompt)

    try:
        client = OpenAI(api_key=key)
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

        result = json.loads(response.choices[0].message.content)
        return result
    except Exception:
        # Fallback to local rule-based parsing if API call fails
        return generate_mock_dag(prompt)

