#!/usr/bin/env python3

import os
import sys
import requests
import json
import traceback
from io import StringIO

# Import the necessary libraries
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.axes import Axes
    import seaborn as sns
    import requests
    import numpy as np
    import time
    import statsmodels.api as sm
    import base64
    import sklearn
    from tabulate import tabulate
    from PIL import Image
    import chardet
except ImportError: # if the libraries are not installed, install them
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", 
                           "pandas", "matplotlib", "seaborn", 
                           "requests", "numpy", "statsmodels", 
                           "base64", "tabulate", "chardet"])
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.axes import Axes
    import seaborn as sns
    import requests
    import numpy as np
    import time
    import statsmodels.api as sm
    import base64
    import sklearn
    from tabulate import tabulate
    import chardet

# Remove or comment out the following line for security
os.environ['AIPROXY_TOKEN'] = 'eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjEwMDE5MDFAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.mJt6NLK8wd3Y_uXAtkfAPm-Lztr51MxnaFGX9v0I1H0'


# ------------------------------------------------------------------------------
# Utils
# ------------------------------------------------------------------------------

def get_data_metadata(
        df: pd.DataFrame
) -> dict:
    """
    Get general information of the dataset.
    
    Parameters
    ----------
    df: pandas DataFrame containing the data.

    Returns
    -------
    dictionary with 
        list of columns (and their datatypes)
        summary statistics such as mean, median, 0.25/0.75 percentile, etc.
        missing values count for each column, and
        first 10 random instances of the data. 
    """
    metadata = {
        "columns": [],
        "dtypes": {},
        "summary_statistics": {},
        "missing_values": {},
        "example_values": {}
    }

    # Column names with their data types
    metadata["columns"] = df.columns.tolist()
    metadata["dtypes"] = df.dtypes.apply(lambda x: x.name).to_dict()

    # Summary statistics for numerical columns
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    metadata["summary_statistics"] = df[numeric_cols].describe().to_dict()

    # Missing values
    metadata["missing_values"] = df.isnull().sum().to_dict()

    # Randomly pick some rows for example
    rand_indexes = np.random.randint(0, df.shape[0], size=(10))
    example_rows = df.iloc[rand_indexes].to_dict(orient='records')
    metadata["example_values"] = example_rows

    return metadata


def make_openai_request(
        api_key: str,
        messages: list,
        model: str ="gpt-4o-mini"
) -> dict:
    """
    Send POST request to the proxy LLM
    
    Parameters
    ----------
    api_key: string with with AIPROXY TOKEN
    messages: list of dictionaries, with each dictionary with
      keys 'role' and 'content'
    model: string to show which model to use for the response; 
      gtp-4o-mini by default
    
    Returns
    -------
    dict: parsed JSON response from the POST request
    """
    
    url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

    # Set up the headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Define the payload
    payload = {
        "model": model,
        "messages": messages
    }

    # Make the POST request
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}")
        # sys.exit(1)
        raise requests.exceptions.HTTPError
    except Exception as err:
        print(f"An error occurred: {err}")
        # sys.exit(1)
    else:
        # Process the response
        data = response.json()
        # print("Response from API:")
        # print(json.dumps(data, indent=2))  # Pretty-print the JSON response
        return data

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        rawdata = f.read()
    result = chardet.detect(rawdata)
    return result['encoding']
    
    # with open(csv_file, 'rb') as f:
    #     result = chardet.detect(f.read())
    # encoding = result['encoding']

def encode_image_to_base64(image_path):
    """
    Encodes an image file to a Base64 string.

    Parameters:
    - image_path (str): Path to the image file.

    Returns:
    - str: Base64-encoded string of the image.
    """
    with open(image_path, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string


def resize_and_compress_image(image_path, output_path, size=(512, 512), quality=70):
    """
    Resize and compress an image.

    Parameters:
    - image_path (str): Path to the original image.
    - output_path (str): Path to save the resized and compressed image.
    - size (tuple): Desired size in pixels (width, height).
    - quality (int): Compression quality (1-100). Lower means more compression.
    """
    try:
        with Image.open(image_path) as img:
            # Resize the image using the new Resampling filter
            img = img.resize(size, Image.Resampling.LANCZOS)
            
            # Compress and save the image
            img.save(output_path, format='PNG', optimize=True, quality=quality)
        print(f"Image resized and compressed: {output_path}")
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")

# ------------------------------------------------------------------------------
# Analysis
# ------------------------------------------------------------------------------

def suggest_analyses(
        api_key: str,
        metadata: dict
) -> list:
    """
    Using the metadata of the dataset, ask the LLM for what kind of analyses can be run
    on the entire dataset for insights.

    Parameters
    ----------
    api_key: string with with AIPROXY TOKEN
    metadata: dictionary containing summaries info of the entire dataset

    Returns
    -------
    list of dictionaries in the format:
        [
            {
                'title': '...', (title of analysis)
                'description': '...', (brief description of analysis)
                'return_type': '...', (type of return from the code; 'image', 'DataFrame', or 'text')
                'code': '...' (python code for the analysis)
            },
            {
                ...
            },
            ...
        ]
    """

    prompt = (
        f'''
        Given the following dataset metadata, suggest specific data analysis functions or steps
        that would provide meaningful insights.
        Include Python code snippets. Make sure to include
        analyses such as Correlation analysis, regression analysis, etc.
        Don't include more than 3 charts.
        Refer to the dataset as `df`.
        Suggest 4-5 different insightful analyses that can be conducted on the dataset.
        \n
        Dataset Metadata:\n{json.dumps(metadata, indent=2)}\n
        '''
        '''
        Please provide your suggestions in a JSON string format with a list of analyses, in a format such that when I run
        `json.loads(response["choices"][0]["message"]["content"])`, it should give me a python list of all the analyses, 
        where each analysis is further a dictionary. Use triple quotes for multiline string, and not backward quotes, like 
        you usually would when giving code.
        Don't write `json` after the triple quotes otherwise. don't add '\n' in the output string or in the code otherwise 
        the code will face issues while running.
        In the analysis, avoid using columns that have a lot of missing values.
        '''
        '''
        format of your output should be a list of analyses where each component is a dictionary.
        In the dictionary, there should be four keys 'title', 'description', 'return_type', and 'code'. If the code is 
        supposed to return an image, mention 'image' in 'return_type'; The return type of each code should either be 
        a DataFrame, text, or an image. 
        In the code, use only these libraries: pandas (alias pd), numpy (alias np), seaborn (alias sns), matplotlib.pyplot (alias plt), and statsmodels (alias sm).
        no need to import the libraries in any of your codes. Assume all these libraries have already been imported.
        Any code that is creating a chart, save the figure under the variable name `resulting_figure` so I can access
        it in my code and save the figure. Keep images small. No more than 500x500px. That's the size of 1 tile. 
        Any code that is creating a dataframe or a statsmodels summary, save the output under the variable name `resulting_data` so I can access
        it in my code and save the data. 
        Don't use multiline strings anywhere in the output. Use double-quoted string for code.
        Suggest basic analysis on the dataset. Make sure the outputs of the codes are either images are the analysis is such that the output should be 
        manageable within 10-15 rows. Don't do analyses that will output the entire dataset.
        '''
    )

    max_iter = 5
    for attempts in range(1, max_iter):
        try:
            # message for the system and on the user's behalf
            messages = [
                {"role": "system", "content": "You are a very resourceful data analyst, who is also highly skilled at coding."},
                {"role": "user", "content": prompt}
            ]

            # send a request with the messages
            response = make_openai_request(api_key, messages)

            suggestions = response["choices"][0]["message"]["content"]
            # Remove triple quotes if present
            if '"""' in suggestions:
                suggestions = suggestions.strip('"""')
            elif "'''" in suggestions:
                suggestions = suggestions.strip("'''")
            analyses = json.loads(suggestions)
            return analyses

        except json.JSONDecodeError:
            if attempts == max_iter - 1:
                print("Error: The response is not valid JSON.")
                print("Response content:", suggestions)
                sys.exit(1)
            else:
                print('Retrying after 5 seconds...')
                time.sleep(5)
        except Exception as e:
            print(f"Error communicating with API: {e}")
            sys.exit(1)


def perform_analysis(
        df: pd.DataFrame, 
        analyses: list, 
        folder_name: str
) -> list:
    """
    Run the code(s) in analyses.

    Parameters
    ----------
    df: pandas DataFrame containing the entire dataset.
    analyses: list of dictionaries, where each dictionary is an analysis.
    folder_name: string of the name of folder where charts are to be saved.

    Returns
    -------
    updated list of analyses, where a new key is added to each dictionary:
    'result': stores the output of the code; or
    'image_b64': stores the Base64-encoded string of the chart.
        [
            {
                ...,
                'result': '...' (JSON string or text)
                'image_b64': '...' (Base64 string, if applicable)
            }
        ]
    """

    max_iter = 5
    for attempts in range(max_iter):
        try:
            for i, analysis in enumerate(analyses):
                print(f"Performing analysis {i+1}/{len(analyses)}: {analysis.get('title', 'No Title')}")

                # get the return type of code
                return_type = analysis['return_type']

                # extract the code
                code = analysis['code']

                # define the libraries and other variables
                globals_dict = {'pd': pd, 'np': np, 'plt': plt, 'sns': sns, 'sm': sm}
                locals_dict = {'df': df}

                # execute the code
                try:
                    exec(code, globals_dict, locals_dict)
                except Exception as e:
                    print(f"Error executing analysis '{analysis.get('title', 'No Title')}': {e}")
                    traceback.print_exc()
                    continue

                if return_type == 'image':
                    # Images/Charts
                    figure = locals_dict.get('resulting_figure')
                    if figure is not None:
                        # Create folder if it doesn't exist
                        os.makedirs(folder_name, exist_ok=True)
                        # Define image paths
                        original_path = os.path.join(folder_name, f'chart_{i}.png')
                        # processed_path = os.path.join(folder_name, f'chart_{i}_processed.png')

                        # Save the original chart
                        if isinstance(figure, Axes):
                            figure = figure.figure
                        figure.savefig(original_path, dpi=100)
                        plt.close(figure)

                        # Resize and compress the image
                        resize_and_compress_image(original_path, original_path)

                        # Convert to Base64
                        chart_b64 = encode_image_to_base64(original_path)

                        # Store the Base64 string in the dictionary
                        analysis['image_b64'] = chart_b64

                        # Optionally, remove the original and processed images to save space
                        # Commenting out the lines below to retain images
                        # os.remove(original_path)
                        # os.remove(processed_path)

                        # Remove the 'result' key if it exists
                        analysis.pop('result', None)
                    else:
                        print(f"Warning: 'resulting_figure' not found in analysis {i}.")
                
                elif return_type == 'DataFrame':
                    # DataFrames
                    data = locals_dict.get('resulting_data')
                    if isinstance(data, pd.DataFrame):
                        # Convert DataFrame to JSON string
                        json_data = data.to_json(orient='records')
                        analysis['result'] = json_data
                    elif hasattr(data, 'as_text'):
                        # If it's a statsmodels summary
                        summary_text = data.as_text()
                        analysis['result'] = summary_text
                    else:
                        print(f"Warning: 'resulting_data' is not a DataFrame in analysis {i}.")
                
                elif return_type == 'text':
                    # Text summaries (e.g., statsmodels summaries)
                    data = locals_dict.get('resulting_data')
                    if isinstance(data, str):
                        analysis['result'] = data
                    else:
                        print(f"Warning: 'resulting_data' is not a string or statsmodels summary in analysis {i}.")

            return analyses

        except Exception as e:
            if attempts == max_iter - 1:
                print(f"Error during analysis: {e}")
                traceback.print_exc()
                sys.exit(1)
            else:
                print('Error occurred during analysis. Retrying after 5 seconds...')
                traceback.print_exc()
                time.sleep(5)


# def perform_analysis(
#         df: pd.DataFrame, 
#         analyses: list, 
#         folder_name: str
# ) -> list:
#     """
#     Run the code(s) in analyses.

#     Parameters
#     ----------
#     df: pandas DataFrame containing the entire dataset.
#     analyses: list of dictionaries, where each dictionary is an analysis.
#     folder_name: string of the name of folder where charts are to be saved.

#     Returns
#     -------
#     updated list of analyses, where a new key is added to each dictionary:
#     'result': stores the output of the code; or
#     'image_b64': stores the Base64-encoded string of the chart.
#         [
#             {
#                 ...,
#                 'result': '...' (JSON string or text)
#                 'image_b64': '...' (Base64 string, if applicable)
#             }
#         ]
#     """

#     max_iter = 5
#     for attempts in range(max_iter):
#         try:
#             for i, analysis in enumerate(analyses):
#                 print(i)
                
#                 # get the return type of code
#                 return_type = analysis['return_type']
                
#                 # extract the code
#                 code = analysis['code']
                
#                 # define the libraries and other variables
#                 globals_dict = {'pd': pd, 'np': np, 'plt': plt, 'sns': sns, 'sm': sm}
#                 locals_dict = {'df': df, 'data': df}
                
#                 # execute the code
#                 try:
#                     exec(code, globals_dict, locals_dict)
                
#                     if return_type == 'image':
                        
#                         # Images/Charts
#                         figure = locals_dict.get('resulting_figure')
#                         if figure is not None:
#                             # Create folder if it doesn't exist
#                             os.makedirs(folder_name, exist_ok=True)
#                             # Save chart to the appropriate directory for later usage
#                             path = os.path.join(folder_name, f'chart_{i}.png')
#                             figure.savefig(path, dpi=100)  # Adjust DPI as needed
#                             plt.close(figure)
#                             # Encode image to base64
#                             resize_and_compress_image(path, path)
#                             chart_b64 = encode_image_to_base64(path)
#                             # Store the Base64 string in the dictionary
#                             analysis['image_b64'] = chart_b64
#                             # Optionally, remove the file path if not needed
#                             analysis.pop('result', None)
#                         else:
#                             print(f"Warning: 'resulting_figure' not found in analysis {i}.")
                    
#                     elif return_type == 'DataFrame':
#                         # DataFrames
#                         data = locals_dict.get('resulting_data')
#                         if isinstance(data, pd.DataFrame):
#                             # Convert DataFrame to JSON string
#                             json_data = data.to_json(orient='records')
#                             analysis['result'] = json_data
#                         else:
#                             print(f"Warning: 'resulting_data' is not a DataFrame in analysis {i}.")
                    
#                     elif return_type == 'text':
#                         # Text summaries (e.g., statsmodels summaries)
#                         data = locals_dict.get('resulting_data')
#                         if isinstance(data, str):
#                             analysis['result'] = data
#                         elif hasattr(data, 'as_text'):
#                             # If it's a statsmodels summary
#                             summary_text = data.as_text()
#                             analysis['result'] = summary_text
#                         else:
#                             print(f"Warning: 'resulting_data' is not a string or statsmodels summary in analysis {i}.")
#                 except:
#                     continue
                
#             return analyses

#         except Exception as e:
#             if attempts == max_iter - 1:
#                 print(f"Error during analysis: {e}")
#                 traceback.print_exc()
#                 sys.exit(1)
#             else:
#                 print('Error occurred. Retrying after 5 seconds...')
#                 traceback.print_exc()
#                 time.sleep(5)


# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------

def summarize_analysis(
        api_key: str,
        metadata: dict,
        analyses: list
) -> str:
    """
    Ask the LLM to summarize the analysis using the outputs.

    Parameters
    ----------
    api_key: string with with AIPROXY TOKEN
    metadata: dictionary containing summaries info of the entire dataset
    analyses: list of dictionaries containing analyses

    Returns
    -------
    String of summary report in Markdown format
    """

    try:
        prompt = (
            "Based on the following dataset metadata and analyses performed, write a very brief story (less than 300 words) that includes:\n"
            "- The analyses carried out.\n"
            "- The insights discovered.\n"
            "- The implications of the findings.\n\n"
            f"Dataset Metadata:\n{json.dumps(metadata, indent=2)}\n\n"
            "Analyses Performed:\n"
            "To add charts in the analysis, if threre is a chart, use the path of the image"
        )
        
        for analysis in analyses:
            
            title = analysis.get('title', 'No Title')
            description = analysis.get('description', 'No Description')
            return_type = analysis.get('return_type', 'unknown')
            result = analysis.get('result', '')
            image_b64 = analysis.get('image_b64', '')

            prompt += f"### {title}\n"
            prompt += f"{description}\n\n"

            if return_type == 'image':
                prompt += f"![{title}](data:image/png;base64,{image_b64})\n\n"
                
            elif return_type == 'DataFrame':
                
                if 'statsmodels' in str(type(result)):
                    # prompt += f"**Data Output:**\n\n{result.as_text()}\n\n"
                    None
                else:
                    try:
                        # Convert DataFrame to Markdown table
                        markdown_table = tabulate(result, headers='keys', tablefmt='pipe', showindex=False)
                        prompt += f"**Data Output:**\n\n{markdown_table}\n\n"
                    except ValueError:
                        # If JSON parsing fails, include the raw string
                        prompt += f"**Data Output:**\n\n{result}\n\n"
            elif return_type == 'text':
                prompt += f"**Summary Output:**\n\n{result}\n\n"

            

        prompt += "Please format the output in Markdown, ensuring that images are properly embedded and tables are neatly formatted."

        messages = [
            {"role": "system", "content": "You are a professional data scientist who writes clear and insightful reports."},
            {"role": "user", "content": prompt}
        ]
        # return prompt
        # print('sending request')
        response = make_openai_request(api_key, messages)
        
        summary = response["choices"][0]["message"]["content"]
        return summary

    except requests.exceptions.HTTPError as e:
        return ""
    except Exception as e:
        print(f"Error communicating with API for summarization: {e}")
        sys.exit(1)

def analyse_outputs(
        api_key: str,
        metadata: dict,
        analyses: list
) -> str:
    
    final_summary = ""
    num = 0
    for analysis in analyses:
        if 'result' in analysis:
            try:
                summary = summarize_analysis(api_key, metadata, [analysis])
                final_summary += f"\n\n\n{summary}"

            except requests.exceptions.HTTPError as e:
                continue

            finally:
                print(f"done, {num}")
                num += 1

    return final_summary


def create_report(
        api_key: str,
        summary: str,
        metadata: dict
) -> str:
    
    prompt = f'''
        Based on the following dataset metadata and analyses performed, write a comprehensive story that includes:\n
            - A brief description of the data received.\n
            - The analyses carried out.\n
            - The insights discovered.\n
            - The implications of the findings.\n\n
            Dataset Metadata:\n{json.dumps(metadata, indent=2)}\n\n
            Summary of all the analyses:\n{summary}\n\n
            Please format the output in Markdown, embedding the images appropriately.\n\n
        Using the collection of all analyses and their summaries, write a comprehensive report of the entire study.
        Please format the output in Markdown, ensuring that images are properly embedded and tables are neatly formatted.
    '''

    messages = [
        {"role": "system", "content": "You are a professional data scientist who writes clear and insightful reports."},
        {"role": "user", "content": prompt}
    ]
    response = make_openai_request(api_key, messages)
    report = response["choices"][0]["message"]["content"]

    return report


def save_readme(summary, folder_name):
    """Save the summary to README.md."""
    try:
        with open(f"{folder_name}/README.md", "w") as f:
            f.write(summary)
        print("README.md has been created successfully.")
    except Exception as e:
        print(f"Error writing README.md: {e}")
        sys.exit(1)


# ------------------------------------------------------------------------------
# Main Application
# ------------------------------------------------------------------------------

def main():
    # Check command-line arguments
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py dataset.csv")
        sys.exit(1)

    # Get csv file address
    csv_file = sys.argv[1]

    # Load API key
    try:
        api_key = os.environ["AIPROXY_TOKEN"]
        print('API key loaded!')

    except KeyError:
        print("Error: The AIPROXY_TOKEN environment variable is not set.")
        sys.exit(1)

    # Read CSV
    try:
        encoding = detect_encoding(csv_file)
        df = pd.read_csv(csv_file, encoding=encoding)
        print('CSV file read!')
        folder, ext = os.path.splitext(csv_file)
    except Exception as e:
        print(f"Error reading the CSV file: {e}")
        sys.exit(1)

    # Get metadata
    metadata = get_data_metadata(df)
    print('Metadata collected!')

    # Ask the LLM for suggestions on analyses
    analyses = suggest_analyses(api_key, metadata)
    if len(analyses) == 1:
        key = list(analyses.keys())[0]
        analyses = analyses[key]
    print('Analyses suggestions from LLM collected!')

    # Perform analyses and generate the relevant charts
    performed_analyses = perform_analysis(df, analyses, folder_name=folder)
    print("Analysis' codes run and results saved!")

    # Summarize analysis into a story
    text_analysis = analyse_outputs(api_key, metadata, performed_analyses)
    print("Brief reports generated for each analysis!")

    # Write and save README.md
    save_readme(text_analysis, folder_name=folder)

if __name__ == "__main__":
    main()





