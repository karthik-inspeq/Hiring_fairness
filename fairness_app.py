import streamlit as st
import pandas as pd
from inspeq.client import InspeqEval
from io import StringIO
from streamlit_ace import st_ace
from typing import Dict, List, Tuple, Any, Annotated
from dataclasses import dataclass
import json
from datetime import datetime
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolExecutor
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv
import os
import ast
import tempfile
from collections import defaultdict, deque
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
import time



load_dotenv() 

if 'api_key' not in st.session_state: st.session_state['api_key'] = None
if 'pdf' not in st.session_state: st.session_state['pdf'] = None
if "embed_model" not in st.session_state: st.session_state['embed_model'] = None
if "vector_store" not in st.session_state: st.session_state['vector_store'] = None
if "metrics" not in st.session_state: st.session_state['metrics'] = None
if "options" not in st.session_state: st.session_state['options'] = []
if "excel" not in st.session_state: st.session_state['excel'] = None
if "threshold" not in st.session_state: st.session_state['threshold'] = None
if "attribute" not in st.session_state: st.session_state['attribute'] = None
if "privileged" not in st.session_state: st.session_state['privileged'] = None
if "un_privileged" not in st.session_state: st.session_state['un_privileged'] = None
if "filtered_data" not in st.session_state: st.session_state['filtered_data'] = None
if "fairness_score" not in st.session_state: st.session_state['fairness_score'] = None
if "percentage" not in st.session_state: st.session_state['percentage'] = None

# for agentic workflow
if "agents" not in st.session_state: st.session_state['agents'] = []
if "requirements" not in st.session_state: st.session_state['requirements'] = None
if "code" not in st.session_state: st.session_state['code'] = None
if "stategraph" not in st.session_state: st.session_state['stategraph'] = None
if "function" not in st.session_state: st.session_state['function'] = None
if "run_workflow" not in st.session_state: st.session_state['run_workflow'] = None
if "run_agentic_workflow" not in st.session_state: st.session_state['run_agentic_workflow'] = None
if "calculate_fairness" not in st.session_state: st.session_state['calculate_fairness'] = None
if "agentic_functions" not in st.session_state: st.session_state['agentic_functions'] = None
if "nodes" not in st.session_state: st.session_state['nodes'] = None
if "json_output" not in st.session_state: st.session_state['json_output'] = None
if "disparate_impact" not in st.session_state: st.session_state['disparate_impact'] = None
if "threshold" not in st.session_state: st.session_state['threshold'] = None
if "executed" not in st.session_state: st.session_state['executed'] = None
if "demographic_parity" not in st.session_state: st.session_state['demographic_parity'] = None
if "agents_submit" not in st.session_state: st.session_state['agents_submit'] = None
if "score_threshold" not in st.session_state: st.session_state['score_threshold'] = None

st.set_page_config(page_title="Agentic workflow demo", layout="wide")


# class WorkflowState(BaseModel):
#     """Overall workflow state"""
#     job_id: Annotated[str, "job_id"] = "default_job_id"
#     job_requirements: Annotated[Dict[str, float], "job_requirements"] = Field(default_factory=dict)
#     api_key: Annotated[str, "api_key"] = "default_api_key"
#     candidates: Annotated[List[Dict], "candidates"] = Field(default_factory=list)
#     analyzed_candidates: Annotated[List[Dict], "analyzed_candidates"] = Field(default_factory=list)
#     current_candidate_index: Annotated[int, "current_candidate_index"] = Field(default=0)
#     errors: Annotated[List[str], "errors"] = Field(default_factory=list)
#     is_complete: Annotated[bool, "is_complete"] = Field(default=False)
    
# def run_python_file(file):
#     if file is not None:
#         # Save the uploaded file temporarily
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
#             temp_file.write(file.read())
#             temp_file_path = temp_file.name
        
#         # Display the uploaded file name
#         st.write(f"Uploaded file: {file.name}")
        
#         # Import and execute the file
#         try:
#             # Execute the file's content
#             with open(temp_file_path, "r") as f:
#                 code = f.read()
#                 exec(code)  # Executes the Python file's content
            
#             st.success("Python file executed successfully.")
#         except Exception as e:
#             st.error(f"Error executing the file: {e}")
def create_csv_from_data(data, filename="processed_data.csv", folder="uploaded_scripts"):
    """
    This function accepts data, processes it, and saves it as a CSV file in the specified folder.
    
    Parameters:
    - data (DataFrame or dict): The data to be saved as CSV. Can be a pandas DataFrame or a dictionary that can be converted to a DataFrame.
    - filename (str): The name of the file to save the data as (default is "processed_data.csv").
    - folder (str): The folder where the CSV will be saved (default is "uploaded_scripts").
    
    Returns:
    - str: The path of the saved CSV file.
    """
    if data is not None:
    # Read the uploaded CSV file into a DataFrame
        data_df = pd.read_csv(data)
    # Ensure the folder exists
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # If the data is in a dictionary format, convert it to a DataFrame
    if isinstance(data_df, dict):
        df = pd.DataFrame(data)
    elif isinstance(data_df, pd.DataFrame):
        df = data_df
    else:
        raise ValueError("The data should be a pandas DataFrame or a dictionary.")
    
    # Define the full path to the file
    file_path = os.path.join(folder, filename)
    
    # Save the DataFrame as a CSV file
    df.to_csv(file_path, index=False)
    
    return file_path
def run_python_file(file, file_name, save_dir="uploaded_scripts"):
    if file is not None:
        # Ensure the save directory exists
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # Save the uploaded file to the specified directory
        save_path = os.path.join(save_dir, file_name)
        with open(save_path, "wb") as saved_file:
            saved_file.write(file)
        
        # Display the uploaded file name and its saved path
        st.write(f"Uploaded file: {file_name}")
        st.write(f"File saved at: {save_path}")
        
        # Import and execute the file
        try:
            # Execute the file's content
            with open(save_path, "r") as f:
                code = f.read()
                exec(code, globals())  # Executes the Python file's content
            
            st.success("Python file executed successfully.")
        except Exception as e:
            st.error(f"Error executing the file: {e}")
def disparate_impact_score(data, group_key="gender", outcome_key="score", threshold=0.5, protected_group=None):
    """
    Compute the Disparate Impact (DI) score from a list of dictionaries.

    Parameters:
        data (list): List of dictionaries containing candidate data.
        group_key (str): Key representing the protected group (default is 'gender').
        outcome_key (str): Key representing the score or outcome (default is 'score').
        threshold (float): Threshold to consider a positive outcome (default is 0.5).
        protected_group (str): Specify a protected group to compute DI relative to this group (optional).

    Returns:
        float: Disparate Impact score.
        dict: Selection rates for all groups.
    """
    from collections import defaultdict

    # Create a dictionary to count positive outcomes and total members for each group
    group_counts = defaultdict(lambda: {"positive": 0, "total": 0})

    # Populate the group counts
    for entry in data:
        group = entry[group_key]
        outcome = entry[outcome_key]
        group_counts[group]["total"] += 1
        if outcome >= threshold:  # Consider scores above threshold as positive outcomes
            group_counts[group]["positive"] += 1

    # Calculate selection rates for each group
    selection_rates = {
        group: counts["positive"] / counts["total"] if counts["total"] > 0 else 0
        for group, counts in group_counts.items()
    }
    best_group = max(selection_rates, key=selection_rates.get) if selection_rates else None
    # Compute Disparate Impact
    if selection_rates:
        if protected_group:
            if protected_group in selection_rates:
                min_rate = selection_rates[protected_group]  # Use the protected group's rate
            else:
                raise ValueError(f"Protected group '{protected_group}' not found in data.")
        else:
            min_rate = min(selection_rates.values())  # Default to the worst-off group

        max_rate = max(selection_rates.values())  # Best-off group
        di_score = min_rate / max_rate if max_rate > 0 else 0
        dp_score = abs(min_rate - max_rate)
    else:
        di_score = 0
        dp_score = 0# No valid selection rates

    return di_score, selection_rates, dp_score, best_group

from collections import defaultdict

def disparate_impact_and_demographic_parity(data, group_key="gender", outcome_key="score", threshold=0.5, protected_group=None, parity_threshold=0.1):
    """
    Compute Disparate Impact (DI) and Demographic Parity (DP) scores for groups.
    
    Parameters:
        data (list): List of dictionaries containing candidate data.
        group_key (str): Key representing the group attribute (default is 'gender').
        outcome_key (str): Key representing the score or outcome (default is 'score').
        threshold (float): Threshold to consider a positive outcome (default is 0.5).
        protected_group (str): Specify a protected group to compute DI and DP relative to this group (optional).
        parity_threshold (float): Tolerance level for Demographic Parity (default is 0.1).
        
    Returns:
        dict: DI scores for all groups.
        dict: DP scores (absolute differences) for all groups.
        dict: Whether each group meets Demographic Parity.
        float: Overall selection rate (used for DI and DP calculations).
    """
    # Create a dictionary to count positive outcomes and total members for each group
    group_counts = defaultdict(lambda: {"positive": 0, "total": 0})

    # Populate the group counts
    for entry in data:
        group = entry[group_key]
        outcome = entry[outcome_key]
        group_counts[group]["total"] += 1
        if outcome >= threshold:  # Positive outcomes above threshold
            group_counts[group]["positive"] += 1

    # Calculate selection rates for each group
    selection_rates = {
        group: counts["positive"] / counts["total"] if counts["total"] > 0 else 0
        for group, counts in group_counts.items()
    }

    # Calculate the overall selection rate (weighted average)
    total_members = sum(counts["total"] for counts in group_counts.values())
    overall_selection_rate = sum(
        (counts["total"] / total_members) * (counts["positive"] / counts["total"] if counts["total"] > 0 else 0)
        for counts in group_counts.values()
    ) if total_members > 0 else 0

    # Compute DI and DP scores
    di_scores = {}
    dp_scores = {}
    dp_parity_check = {}
    
    for group, rate in selection_rates.items():
        di_scores[group] = rate / overall_selection_rate if overall_selection_rate > 0 else 0
        dp_scores[group] = abs(rate - overall_selection_rate) if overall_selection_rate > 0 else 0
        dp_parity_check[group] = dp_scores[group] <= parity_threshold  # Check if within tolerance

    # Handle specific protected group
    if protected_group:
        if protected_group not in di_scores:
            raise ValueError(f"Protected group '{protected_group}' not found in data.")
        di_scores = {protected_group: di_scores[protected_group]}
        dp_scores = {protected_group: dp_scores[protected_group]}
        dp_parity_check = {protected_group: dp_parity_check[protected_group]}

    return di_scores, dp_scores, dp_parity_check, overall_selection_rate, selection_rates


def compute_fairness_metrics(data, group_key="gender", outcome_key="score", ground_truth_key="ground_truth", threshold=0.5, score_threshold=0.5, protected_group=None, parity_threshold=0.1):
    """
    Compute Disparate Impact (DI), Demographic Parity (DP), Predictive Equality Difference (PED), 
    and Equalized Odds Difference (EOD) scores for groups.
    
    Parameters:
        data (list): List of dictionaries containing candidate data.
        group_key (str): Key representing the group attribute (default is 'gender').
        outcome_key (str): Key representing the score or outcome (default is 'score').
        ground_truth_key (str): Key representing the ground truth labels.
        threshold (float): Threshold to consider a positive outcome (default is 0.5).
        score_threshold (float): Score threshold for categorizing outcomes (default is 0.5).
        protected_group (str): Specify a protected group to compute metrics relative to this group (optional).
        parity_threshold (float): Tolerance level for Demographic Parity (default is 0.1).
        
    Returns:
        dict: DI scores for all groups.
        dict: DP scores (absolute differences) for all groups.
        dict: PED scores for all groups.
        dict: EOD scores for all groups.
        dict: Whether each group meets Demographic Parity.
        float: Overall selection rate (used for DI and DP calculations).
        dict: True Positive Rates (TPR) and False Positive Rates (FPR) for each group.
    """
    # Create dictionaries to track counts
    group_counts = defaultdict(lambda: {"positive": 0, "total": 0, "true_positive": 0, "false_positive": 0, "false_negative": 0, "true_negative": 0})
    
    # Populate the group counts
    for entry in data:
        group = entry[group_key]
        outcome = 1 if entry[outcome_key] >= score_threshold else 0
        ground_truth = 1 if entry[ground_truth_key] >= score_threshold else 0
        
        group_counts[group]["total"] += 1
        if outcome == 1:
            group_counts[group]["positive"] += 1
            if ground_truth == 1:
                group_counts[group]["true_positive"] += 1
            else:
                group_counts[group]["false_positive"] += 1
        else:
            if ground_truth == 1:
                group_counts[group]["false_negative"] += 1
            else:
                group_counts[group]["true_negative"] += 1

    # Calculate selection rates, TPR, and FPR for each group
    selection_rates = {}
    true_positive_rates = {}
    false_positive_rates = {}
    group_sizes = {}
    
    for group, counts in group_counts.items():
        total = counts["total"]
        positive_outcomes = counts["positive"]
        true_positives = counts["true_positive"]
        false_positives = counts["false_positive"]
        true_negatives = counts["true_negative"]
        false_negatives = counts["false_negative"]

        group_sizes[group] = total
        selection_rates[group] = positive_outcomes / total if total > 0 else 0
        true_positive_rates[group] = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        false_positive_rates[group] = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0
    
    # Calculate the overall selection rate (weighted average)
    total_members = sum(group_sizes.values())
    overall_selection_rate = sum(
        (group_sizes[group] / total_members) * selection_rates[group]
        for group in group_sizes
    ) if total_members > 0 else 0

    # Compute metrics
    di_scores = {}
    dp_scores = {}
    ped_scores = {}
    eod_scores = {}
    dp_parity_check = {}

    for group in group_counts.keys():
        rate = selection_rates[group]
        
        # Disparate Impact
        di_scores[group] = rate / overall_selection_rate if overall_selection_rate > 0 else 0
        # Demographic Parity
        dp_scores[group] = abs(rate - overall_selection_rate) if overall_selection_rate > 0 else 0
        dp_parity_check[group] = dp_scores[group] <= parity_threshold

        # Weighted averages for PED and EOD
        if protected_group and protected_group in group_sizes:
            other_groups = [g for g in group_sizes if g != protected_group]
            other_weights = {g: group_sizes[g] / (total_members - group_sizes[protected_group]) for g in other_groups}
            
            weighted_avg_tpr = sum(true_positive_rates[g] * other_weights[g] for g in other_groups if g in true_positive_rates)
            weighted_avg_fpr = sum(false_positive_rates[g] * other_weights[g] for g in other_groups if g in false_positive_rates)
            
            ped_scores[group] = abs(true_positive_rates[group] - weighted_avg_tpr)
            eod_scores[group] = 0.5 * (
                abs(true_positive_rates[group] - weighted_avg_tpr) +
                abs(false_positive_rates[group] - weighted_avg_fpr)
            )
        else:
            ped_scores[group] = 0
            eod_scores[group] = 0

    # Handle specific protected group
    if protected_group:
        if protected_group not in di_scores:
            raise ValueError(f"Protected group '{protected_group}' not found in data.")
        di_scores = {protected_group: di_scores[protected_group]}
        dp_scores = {protected_group: dp_scores[protected_group]}
        ped_scores = {protected_group: ped_scores[protected_group]}
        eod_scores = {protected_group: eod_scores[protected_group]}
        dp_parity_check = {protected_group: dp_parity_check[protected_group]}

    return di_scores, dp_scores, ped_scores, eod_scores, dp_parity_check, overall_selection_rate, selection_rates, (true_positive_rates, false_positive_rates)

def extract_agent_names_from_code(code: str):
    """
    Extract agent names from LangGraph workflow code in execution order.
    """
    # Parse the code into an AST
    tree = ast.parse(code)

    # Dependency graph for agents
    graph = defaultdict(list)
    entry_point = None

    # Traverse the AST nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "set_entry_point":
                # Extract the entry point
                if node.args and isinstance(node.args[0], ast.Constant):
                    entry_point = node.args[0].value
            elif node.func.attr == "add_edge":
                # Extract edges
                if (
                    len(node.args) >= 2
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[1], ast.Constant)
                ):
                    from_agent = node.args[0].value
                    to_agent = node.args[1].value
                    graph[from_agent].append(to_agent)

    # Perform topological sort to get the execution order
    if entry_point is None:
        raise ValueError("Entry point not found in the workflow.")

    visited = set()
    execution_order = []

    def dfs(agent):
        if agent not in visited:
            visited.add(agent)
            for neighbor in graph[agent]:
                dfs(neighbor)
            execution_order.append(agent)

    dfs(entry_point)
    return execution_order[::-1]

def create_agent_flow(llm, data,nodes):
    workflow = StateGraph(WorkflowState)
    nodes = {
        "fetch": lambda x: fetch_candidates(x, data)
        # "analyze": lambda x: analyze_resume(x, llm),
        # "score": lambda x: calculate_scores(x, llm),
    }
    # Add nodes in sequence - each node processes state and passes it to next
    for node_name, node_func in nodes.items():
        workflow.add_node(node_name, node_func)
    agent_sequence = [k for k in nodes.keys()]
    workflow.set_entry_point(agent_sequence[0])
    
    # Create linear flow
    for i in range(len(agent_sequence) - 1):
        workflow.add_edge(agent_sequence[i], agent_sequence[i + 1])
    return workflow.compile()
def create_agent_function(agent_code: str, function_name: str):
    exec(st.session_state["stategraph"])
    local_vars = {"WorkflowState": WorkflowState}
    exec(agent_code, {}, local_vars)
    return local_vars[function_name]

def create_screening_workflow(llm: ChatOpenAI, df, agents) -> Graph:
    """Create the resume screening workflow using user-defined agents."""
    workflow = StateGraph(st.session_state["stategraph"])
    count = 0
    # Dynamically create and register functions from agents
    for agent in agents:
        count += 1
        agent_func = create_agent_function(agent["code"], agent["function"])
        print("agent_func is")
        print(agent_func)
        if count == 1:
            workflow.add_node(agent["agent_name"], lambda x: agent_func(x, df))
        else:
            workflow.add_node(agent["agent_name"], lambda x: agent_func(x, llm))

    # Create linear flow by connecting nodes
    # Assuming a linear flow based on agent order
    for i in range(len(agents) - 1):
        workflow.add_edge(agents[i]["agent_name"], agents[i + 1]["agent_name"])
    
    # Set the entry point to the first agent
    if agents:
        workflow.set_entry_point(agents[0]["agent_name"])

    return workflow.compile()
    
def csv_uploader(uploaded_file):
    if uploaded_file is not None:
        # Can be used wherever a "file-like" object is accepted:
        dataframe = pd.read_csv(uploaded_file)
        return dataframe

def main():
    st.markdown("""## Inspeq Fairness Demo for Hiring""")
    with st.sidebar:
        st.title("Menu:")
        if "agents" not in st.session_state:  # Ensure session state is initialized
            st.session_state["agents"] = []
        st.write("Make sure the agentic workflow, returns a json file in the following format:")
        st.json(body=
                    {
            "id": int,
            "resume_text": str,
            "attribute1": str,
            "attribute2": str,
            "score": float
        }
        )
        with st.form("agents_form"):
            st.session_state["agentic_functions"] = st.file_uploader("Upload a Python file containing agentic functions", type=["py"])
            st.session_state["resume_data"] = st.file_uploader("Upload a Python file containing agentic functions", type=["csv"])
            st.session_state["agents_submit"] = st.form_submit_button("Run Agentic workflow")
        
        with st.form("fairness_form"):
            st.session_state["json_output"] = st.file_uploader("Upload the JSON file containing the results", type=["json"])
            st.session_state["attribute"] = st.text_input(label="Enter Attribute", placeholder="e.g., gender, age, etc.")
            st.session_state["un_privileged"] = st.text_input(label="Enter group to calculate fairness", placeholder="e.g., female, minority group, etc.")
            st.session_state["threshold"] = st.text_input(label="Enter the threshold above which a candidate is considered", placeholder="e.g., 0.5")
            st.session_state["score_threshold"] = st.text_input(label="Enter the threshold above which a candidate is selected", placeholder="e.g., 0.5")
            # Submit button for the form
            st.session_state["run_workflow"]= st.form_submit_button("Calculate Fairness")

    # Enters code
    if st.session_state["agents_submit"] and st.session_state["agentic_functions"] and st.session_state["resume_data"]:
        # The above code is running a Python file that is stored in the `agentic_functions` key of the
        # Streamlit session state (`st.session_state`).
        create_csv_from_data(st.session_state["resume_data"])
        code_content = st.session_state["agentic_functions"].read()
        # run_python_file(code_content, st.session_state['agentic_functions'].name)
        # Read the uploaded file
        try:
            # Ensure the file's content is read as a string
            # Extract agent names from the code
            st.session_state['agents'] = extract_agent_names_from_code(code_content.decode('utf-8'))
            st.success("Agents extracted successfully!")
        except Exception as e:
            st.error(f"Error processing file: {e}")

    if st.session_state['run_workflow']:
        data = json.load(st.session_state["json_output"])
        # st.session_state['disparate_impact'] = disparate_impact_and_demographic_parity(data, st.session_state['attribute'], outcome_key='score', threshold=float(st.session_state["threshold"]), protected_group=st.session_state['un_privileged'])
        st.session_state['disparate_impact'] = compute_fairness_metrics(data, group_key="gender", outcome_key="score", ground_truth_key="ground_truth", threshold= float(st.session_state["threshold"]), score_threshold = float(st.session_state["score_threshold"]), protected_group=st.session_state['un_privileged'], parity_threshold=0.1)
        # st.write("The Disparate impact score is")
        # if st.session_state['disparate_impact'][-1] != st.session_state['un_privileged']:
        #     st.markdown(f"""
        #         <div style="display: flex; justify-content: space-around; align-items: center;">
        #             <div style="text-align: center; font-size: 36px; font-weight: bold; color: #4CAF50;">
        #                 <div>Disparate Impact</div>
        #                 <div>{st.session_state['disparate_impact'][0]}</div>
        #             </div>
        #             <div style="text-align: center; font-size: 36px; font-weight: bold; color: #2196F3;">
        #                 <div>Demographic Parity</div>
        #                 <div>{st.session_state['disparate_impact'][-2]}</div>
        #             </div>
        #         </div>
        #     """, unsafe_allow_html=True)
        # else:
        #     st.markdown(f"""
        #         <div style="display: flex; justify-content: space-around; align-items: center;">
        #             <div style="text-align: center; font-size: 36px; font-weight: bold; color: #4CAF50;">
        #                 <div>"{st.session_state['un_privileged']}" group has higher selection rate at {st.session_state["disparate_impact"][1][st.session_state["un_privileged"]]}</div>""", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="display: flex; justify-content: space-around; align-items: center;">
                <div style="text-align: center; font-size: 36px; font-weight: bold; color: #4CAF50;">
                    <div>Disparate Impact</div>
                    <div>{st.session_state['disparate_impact'][0][st.session_state["un_privileged"]]}</div>
                </div>
                <div style="text-align: center; font-size: 36px; font-weight: bold; color: #2196F3;">
                    <div>Demographic Parity</div>
                    <div>{round(st.session_state['disparate_impact'][1][st.session_state['un_privileged']], 2)}</div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-around; align-items: center;">
                <div style="text-align: center; font-size: 36px; font-weight: bold; color: #4CAF50;">
                    <div>PED</div>
                    <div>{round(st.session_state['disparate_impact'][2][st.session_state["un_privileged"]], 3)}</div>
                </div>
                <div style="text-align: center; font-size: 36px; font-weight: bold; color: #2196F3;">
                    <div>EOD</div>
                    <div>{round(st.session_state['disparate_impact'][3][st.session_state['un_privileged']], 2)}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        df = pd.DataFrame(list(st.session_state['disparate_impact'][-2].items()), columns=[f"{st.session_state['attribute']}", "Selection Rates"])
        st.write(df)
    nodes = []
    edges = []
    for i, node in zip(range(len(st.session_state['agents'])),st.session_state["agents"]):
        flow_node = StreamlitFlowNode(
            id=f"{i}",  # Unique ID for each node
            pos=(100 * i, 100),  # Position (x, y)
            data={'content': node},  # Display content
            node_type='default',  # Node type
            source_position='right',  # Source connection
            target_position='left',  # Target connection
            draggable=True  # Allow dragging
            )
        nodes.append(flow_node)
        if (i+1) < len(st.session_state['agents']):
            edge_node = StreamlitFlowEdge(f'{i}-{i+1}', f'{i}', f'{i+1}',animated = True, marker_end={'type': 'arrow'})
            edges.append(edge_node)

    state = StreamlitFlowState(nodes, edges)
    if st.session_state['agents']:
        streamlit_flow('static_flow',
                        state,
                        fit_view=True,
                        show_minimap=False,
                        show_controls=False,
                        pan_on_drag=False,
                        allow_zoom=False)

        
        
if __name__ == "__main__":
    main()
