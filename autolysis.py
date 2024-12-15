# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx",
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "tenacity",
#   "tabulate",
#   "requests",
# ]
# ///

import os
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import sys
import requests

# Environment variable setup
API_TOKEN = os.environ["AIPROXY_TOKEN"]
API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"  # Ensure this is set to your API endpoint
if not API_TOKEN:
    raise EnvironmentError("API_TOKEN environment variable is not set.")

# Global Constants
MODEL = "gpt-4o-mini"

# Utility Functions
def read_dataset(file_path):
    """Load dataset and handle potential errors."""
    try:
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding='ISO-8859-1')
    except Exception as e:
        raise RuntimeError(f"Error loading dataset: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def query_llm(context=None):
    """Query the LLM for insights using the external API proxy."""

    full_prompt = f"""
    Using the following data analysis, craft an engaging and informative narrative. The story should be clearly structured, with multiple paragraphs, with a beginning, middle, and end while making the data analysis both interesting and accessible.
    
    Context:
    
    {context}
    
    Prompt:
    
    Generate a nice and creative story from the analysis. The story should include the following elements:
    - A captivating introduction that outlines the purpose and significance of the data.
    - A comprehensive body that breaks down the key findings, explaining their importance and relevance.
    - A concluding section that summarizes the main points and offers any conclusions, suggestions, or potential outcomes.
    - Seamless transitions between sections to ensure a smooth and coherent flow throughout the story.
    - Clear organization into distinct paragraphs, allowing the reader to easily follow the progression.
    - Emphasize the key data points in a way that connects them to practical examples or real-world applications.
    - 
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    try:
        # Send the POST request to the proxy
        response = requests.post(API_URL, headers=headers, data=json.dumps(data))

        if response.status_code == 200:
            # Extract the story from the response
            story = response.json()['choices'][0]['message']['content'].strip()
            print("Story generated.")  # Debugging line
            return story
        else:
            print(f"Error with request: {response.status_code} - {response.text}")
            return "Failed to generate story."
    except Exception as e:
        print(f"Error: {e}")
        return "Failed to generate story."

# Analysis Functions
def basic_analysis(df):
    """Generate summary statistics and missing value report."""
    summary = df.describe(include='all').to_dict()
    missing = df.isnull().sum().to_dict()
    return summary, missing

def correlation_matrix(df):
    """Generate a correlation matrix for numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    return numeric_df.corr() if not numeric_df.empty else pd.DataFrame()

def detect_outliers(df):
    """Identify outliers using the IQR method."""
    numeric_df = df.select_dtypes(include=[np.number])
    Q1 = numeric_df.quantile(0.25)
    Q3 = numeric_df.quantile(0.75)
    IQR = Q3 - Q1
    return ((numeric_df < (Q1 - 1.5 * IQR)) | (numeric_df > (Q3 + 1.5 * IQR))).sum()

# Visualization Functions
def save_correlation_heatmap(corr, output_path):
    if not corr.empty:
        plt.figure(figsize=(10, 10))
        sns.heatmap(corr, annot=True, cmap='coolwarm', fmt='.2f')
        plt.title('Correlation Matrix')
        plt.savefig(output_path)
        plt.close()

def save_outlier_plot(outliers, output_path):
    if outliers.sum() > 0:
        outliers.plot(kind='bar', color='red', figsize=(10, 10))
        plt.title('Outliers Count by Feature')
        plt.savefig(output_path)
        plt.close()

def save_distribution_plot(df, output_path):
    numeric_columns = df.select_dtypes(include=[np.number])
    if not numeric_columns.empty:
        sns.histplot(numeric_columns.iloc[:, 0], kde=True, bins=30)
        plt.title('Distribution of First Numeric Column')
        plt.savefig(output_path)
        plt.close()

# Report Creation
def create_readme(output_dir, summary, missing, corr_path, outliers_path, dist_path, context=None):
    readme_path = os.path.join(output_dir, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("# 🌟 Data Analysis Report 🌟\n\n")
        # Convert summary JSON into a markdown table
        summary_df = pd.DataFrame(summary)
        f.write(summary_df.to_markdown(index=True))
        f.write("\n\n")

        f.write("## 🔍 Missing Values\n")
        f.write("Unveiling the gaps in our dataset, below are the missing value counts for each column:\n\n")
        
        # Convert missing values JSON into a markdown table
        missing_df = pd.DataFrame(list(missing.items()), columns=["Column", "Missing Values"])
        f.write(missing_df.to_markdown(index=False))
        f.write("\n\n")

        f.write("## 🎨 Visualizations\n")
        f.write("Visual insights into our data:\n\n")
        f.write(f"### Correlation Heatmap\n")
        f.write("![Correlation Matrix](correlation_matrix.png)\n\n")
        f.write(f"### Outliers Detected\n")
        f.write("![Outliers](outliers.png)\n\n")
        f.write(f"### Data Distribution\n")
        f.write("![Distribution](distribution.png)\n\n")

        if context:
            f.write("## ✨ Story\n")
            f.write("Step into a narrative journey inspired by the dataset:\n\n")
            f.write(context)

        f.write("\n## 📘 Conclusion\n")
        f.write("Through this report, we unravel the patterns and anomalies present in the dataset. From statistical revelations to visual storytelling, each element contributes to a deeper understanding of the data at hand.\n")

    return readme_path

# Main Function
def main(file_path):
    output_dir = os.path.splitext(file_path)[0]
    os.makedirs(output_dir, exist_ok=True)

    df = read_dataset(file_path)
    summary, missing = basic_analysis(df)
    corr = correlation_matrix(df)
    outliers = detect_outliers(df)

    corr_path = os.path.join(output_dir, 'correlation_matrix.png')
    outliers_path = os.path.join(output_dir, 'outliers.png')
    dist_path = os.path.join(output_dir, 'distribution.png')

    save_correlation_heatmap(corr, corr_path)
    save_outlier_plot(outliers, outliers_path)
    save_distribution_plot(df, dist_path)

    story = query_llm(context=json.dumps(summary, indent=4))

    readme_path = create_readme(output_dir, summary, missing, corr_path, outliers_path, dist_path, story)

    print(f"Analysis complete. Report generated at {readme_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run autolysis.py <dataset_path>")
        sys.exit(1)
    main(sys.argv[1])
