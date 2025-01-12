import sys
import pkg_resources
from typing import Dict, List, Tuple, Any, Annotated
from dataclasses import dataclass
import json
from datetime import datetime
import PyPDF2
import io
import logging
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolExecutor
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import requests
import json
from typing import Dict
from langchain.schema import HumanMessage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkflowState(BaseModel):
    """Overall workflow state"""
    job_id: Annotated[str, "job_id"]
    job_requirements: Annotated[Dict[str, float], "job_requirements"]
    api_key: Annotated[str, "api_key"]
    candidates: Annotated[List[Dict], "candidates"] = Field(default_factory=list)
    analyzed_candidates: Annotated[List[Dict], "analyzed_candidates"] = Field(default_factory=list)
    current_candidate_index: Annotated[int, "current_candidate_index"] = Field(default=0)
    errors: Annotated[List[str], "errors"] = Field(default_factory=list)
    is_complete: Annotated[bool, "is_complete"] = Field(default=False)
    
def fetch_candidates(state: WorkflowState, df) -> WorkflowState:
    """Node to fetch candidates from Dover"""
    try:
        # dover_api = DoverAPI(state.api_key)
        # candidates = dover_api.get_candidates(state.job_id)
        # candidates = df[df["Category"] == state.job_id]["ID"].to_list()
        new_df = df[df["Category"] == state.job_id][:10]
        candidates = []
        for _, row in new_df.iterrows():
          candidate = {
              "category": row["Category"],
              "resume": row["Resume"]
          }
          candidates.append(candidate)

        # Create new state with fetched candidates
        return WorkflowState(
            job_id=state.job_id,
            job_requirements=state.job_requirements,
            api_key=state.api_key,
            candidates=candidates,
            analyzed_candidates=[],
            current_candidate_index=0,
            is_complete=False,
            errors=state.errors
        )
    except Exception as e:
        return WorkflowState(
            job_id=state.job_id,
            job_requirements=state.job_requirements,
            api_key=state.api_key,
            errors=[f"Error fetching candidates: {str(e)}"]
        )
def process_candidate(state: WorkflowState) -> WorkflowState:
    """Node to process the current candidate"""
    if state.current_candidate_index >= len(state.candidates):
        state.is_complete = True
        return state

    try:
        current_candidate = state.candidates[state.current_candidate_index]
        dover_api = DoverAPI(state.api_key)

        # Get resume
        resume_content = dover_api.get_resume(current_candidate['id'])
        resume_text = extract_text_from_pdf(resume_content)

        # Create analysis state
        analysis = {
            'candidate_id': current_candidate['id'],
            'name': f"{current_candidate['first_name']} {current_candidate['last_name']}",
            'email': current_candidate['email'],
            'resume_text': resume_text,
            'analysis': {},
            'score': 0.0,
            'reasoning': ''
        }

        state.analyzed_candidates.append(analysis)
        state.current_candidate_index += 1

    except Exception as e:
        state.errors.append(f"Error processing candidate: {str(e)}")

    return state
def analyze_resume(state: WorkflowState, llm: ChatOpenAI) -> WorkflowState:
    """
    Node to analyze candidates' resumes and add the analysis to the state.
    """
    if state.is_complete:
        return state

    try:
        analyzed_candidates = []
        for candidate in state.candidates:
            # Construct the prompt for the LLM
            prompt = f"""
            Analyze the following resume text against the job requirements.

            **Job Requirements:**
            {json.dumps(state.job_requirements, indent=2)}

            **Candidate's Resume:**
            {candidate['resume']}

            Provide a detailed analysis including:
            1. Skills match (score 0-1)
            2. Experience relevance (score 0-1)
            3. Key strengths
            4. Areas of concern
            5. Overall recommendation (Hire/Consider/Reject)
            """

            # Call the LLM for analysis
            response = llm.invoke([HumanMessage(content=prompt)])
            analysis = response.content.strip()

            # Add the analysis to the candidate's data
            analyzed_candidate = {
                "id": candidate["id"],
                "resume_text": candidate["resume"],
                "gender": candidate.get("gender", "Unknown"),
                "analysis": analysis
            }
            analyzed_candidates.append(analyzed_candidate)

        # Update the state with analyzed candidates
        state.analyzed_candidates = analyzed_candidates
        state.is_complete = True  # Mark as complete when all candidates are analyzed

    except Exception as e:
        state.errors.append(f"Error analyzing resumes: {str(e)}")

    return state
def extract_scores(analysis_text: str, llm: ChatOpenAI) -> Dict[str, float]:
    """
    Extract scores for 'Skills Match' and 'Experience Relevance' from the analysis text using an LLM.

    Parameters:
        analysis_text (str): The text containing the analysis.
        llm (ChatOpenAI): The LLM to process the analysis text.

    Returns:
        dict: A dictionary with extracted scores, or default values if not found.
    """
    # try:
        # Construct the prompt for the LLM
    prompt = f"""
    Extract the following numerical scores from the provided analysis text:

    1. Skills Match (score 0-1)
    2. Experience Relevance (score 0-1)

    If a score is missing or unclear, return 0.0 as the default.

    **Analysis Text:**
    {analysis_text}

    Return the scores as a JSON object with keys: "skills_match" and "experience_relevance".
    """

    # Invoke the LLM
    response = llm.invoke([HumanMessage(content=prompt)])
    extracted_scores = response.content.strip()
    print(extracted_scores)
    json_pattern = r"\{.*?\}"
    match = re.search(json_pattern, extracted_scores, re.DOTALL) 
    if match:
        json_str = match.group(0)  # Extract the matched JSON string
        try:
            # Parse the JSON string into a Python dictionary
            parsed_json = json.loads(json_str)
            return parsed_json
        except json.JSONDecodeError:
            print("Detected JSON, but it could not be parsed.")
            return None
    else:
        print("No JSON object detected.")
        return None
    # Parse the LLM response into a dictionary

    # except Exception as e:
    #     print(f"Error extracting scores with LLM: {str(e)}")
    #     # Return default scores in case of an error
    #     return {"skills_match": 0.0, "experience_relevance": 0.0}
analysis_text = """
**1. Skills Match (score 0-1):** 0.1

The candidate's resume does not directly mention or imply expertise in the specific technical skills required for the job, such as Python, machine learning, SQL, AWS, Docker, or API development. The only somewhat relevant skill mentioned is "data analysis," but it is not detailed enough to assess proficiency or relevance to the level required for the job. Therefore, the score is very low.

**2. Experience Relevance (score 0-1):** 0.1

The candidate's experience is primarily in customer service, HR, marketing, and administrative roles, with no direct experience in technical or development roles that would be relevant to the job requirements. While some transferable skills such as analytical skills and data analysis are mentioned, they are not in the context of the technical and specialized nature of the job. Thus, the relevance is minimal.

**3. Key Strengths:**

- **Customer Service and HR Experience:** The candidate has extensive experience in customer service and human resources, indicating strong interpersonal and communication skills.
- **Analytical Skills:** Mention of data analysis and medical billing analysis suggests the candidate possesses some level of analytical skills, which are valuable in many roles.
- **Marketing and Public Relations:** Experience in marketing and creating marketing collateral shows creativity and an understanding of market dynamics.

**4. Areas of Concern:**

- **Lack of Technical Skills:** The candidate does not demonstrate the required technical skills such as Python, machine learning, SQL, AWS, Docker, or API development.
- **Irrelevant Experience:** The bulk of the candidate's experience is in fields unrelated to the technical nature of the job, making it a significant mismatch.
- **No Mention of Relevant Education or Training:** There is no mention of education or training in computer science, data science, or related fields that would be necessary for the job.

**5. Overall Recommendation: Reject**

Given the significant gap between the candidate's skills and experience and the job requirements, the recommendation is to reject. The candidate does not possess the technical skills or relevant experience for the role. While they have strengths in customer service, HR, and marketing, these do not align with the technical and specialized nature of the position. It would be beneficial for the candidate to pursue relevant education and gain experience in the required technical areas before applying for such roles.
--------------------------------------------------
"""
# Initialize LLM
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model="gpt-4-turbo-preview",
    temperature=0
)
scores = extract_scores(analysis_text=analysis_text, llm=llm)
scores

def calculate_scores(state: WorkflowState, llm: ChatOpenAI) -> WorkflowState:
    """Node to calculate final scores for all candidates."""
    if not state.is_complete:
        return state

    try:
        for candidate in state.analyzed_candidates:
            # Extract scores dynamically from analysis
            analysis_text = candidate['analysis']
            extracted_scores = extract_scores(analysis_text, llm)

            skills_score = extracted_scores['skills_match']
            exp_score = extracted_scores['experience_relevance']

            # Weighted scoring
            candidate['score'] = (skills_score * 0.6) + (exp_score * 0.4)

        # Sort candidates by score
        state.analyzed_candidates.sort(key=lambda x: x['score'], reverse=True)

    except Exception as e:
        state.errors.append(f"Error calculating scores: {str(e)}")

    return state

def generate_reasoning(state: WorkflowState, llm: ChatOpenAI) -> WorkflowState:
    """Generate reasoning for candidate analysis"""
    try:
        current_analysis = state.analyzed_candidates[-1]
        prompt = f"""
        Based on the following analysis, provide a concise reasoning for the candidate's ranking:

        Skills Analysis: {current_analysis.get('analysis', {})}
        Score: {current_analysis.get('score', 0)}

        Provide a brief professional explanation for this ranking.
        """

        response = llm.invoke([HumanMessage(content=prompt)])
        current_analysis['reasoning'] = response.content

        return state

    except Exception as e:
        state.errors.append(f"Error generating reasoning: {str(e)}")
        return state
def create_screening_workflow(llm: ChatOpenAI, df) -> Graph:
    """Create the resume screening workflow"""
    # Define state shape for the nodes to run in sequence
    nodes = {
        "fetch": lambda x: fetch_candidates(x, df),
        "analyze": lambda x: analyze_resume(x, llm),
        "score": lambda x: calculate_scores(x, llm),
        "reason": lambda x: generate_reasoning(x, llm)
    }

    workflow = StateGraph(WorkflowState)

    # Add nodes in sequence - each node processes state and passes it to next
    for node_name, node_func in nodes.items():
        workflow.add_node(node_name, node_func)

    # Create linear flow
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "analyze")
    workflow.add_edge("analyze", "score")
    workflow.add_edge("score", "reason")

    return workflow.compile()
    



