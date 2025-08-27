import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import requests
from io import StringIO

# Set page configuration
st.set_page_config(
    page_title="GitHub Copilot Metrics Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #1f77b4;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def load_data(uploaded_file):
    """Load and parse the JSON data"""
    try:
        data = json.load(uploaded_file)
        return data
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
        return None

def fetch_github_copilot_data(api_token, start_date, end_date, org_name="reizendai"):
    """Fetch Copilot metrics data from GitHub API"""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {api_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    api_url = f"https://api.github.com/orgs/{org_name}/copilot/metrics?since={start_date}&until={end_date}"
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from GitHub API: {e}")
        if response.status_code == 401:
            st.error("Authentication failed. Please check your GitHub API token.")
        elif response.status_code == 403:
            st.error("Permission denied. Please ensure your token has the required scopes.")
        elif response.status_code == 404:
            st.error("Organization not found or Copilot metrics not available.")
        return None

def flatten_data(data):
    """Flatten the nested JSON structure into a pandas DataFrame"""
    flattened_data = []
    
    for day in data:
        date = day['date']
        
        # IDE Chat metrics
        ide_chat_users = day.get('copilot_ide_chat', {}).get('total_engaged_users', 0)
        
        # Code completions metrics
        code_completion_users = day.get('copilot_ide_code_completions', {}).get('total_engaged_users', 0)
        
        # Dotcom Chat metrics
        dotcom_chat_users = day.get('copilot_dotcom_chat', {}).get('total_engaged_users', 0)
        
        # Pull Request metrics
        pr_users = day.get('copilot_dotcom_pull_requests', {}).get('total_engaged_users', 0)
        
        # Total metrics
        total_active_users = day.get('total_active_users', 0)
        total_engaged_users = day.get('total_engaged_users', 0)
        
        # Extract language-specific data if available
        languages_data = day.get('copilot_ide_code_completions', {}).get('languages', [])
        language_usage = {lang['name']: lang.get('total_engaged_users', 0) for lang in languages_data}
        
        # Extract editor-specific data
        editors_data = day.get('copilot_ide_code_completions', {}).get('editors', [])
        editor_usage = {}
        for editor in editors_data:
            editor_name = editor['name']
            editor_usage[editor_name] = editor.get('total_engaged_users', 0)
        
        # Create a flattened record
        record = {
            'date': date,
            'ide_chat_users': ide_chat_users,
            'code_completion_users': code_completion_users,
            'dotcom_chat_users': dotcom_chat_users,
            'pr_users': pr_users,
            'total_active_users': total_active_users,
            'total_engaged_users': total_engaged_users,
            **language_usage,
            **{f'editor_{k}': v for k, v in editor_usage.items()}
        }
        
        flattened_data.append(record)
    
    return pd.DataFrame(flattened_data)

def create_summary_metrics(df):
    """Create summary metrics cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Days", len(df))
        st.metric("Avg. Active Users", round(df['total_active_users'].mean(), 1))
    
    with col2:
        st.metric("Max Active Users", df['total_active_users'].max())
        st.metric("Avg. Engaged Users", round(df['total_engaged_users'].mean(), 1))
    
    with col3:
        st.metric("Max IDE Chat Users", df['ide_chat_users'].max())
        st.metric("Max Code Completion Users", df['code_completion_users'].max())
    
    with col4:
        st.metric("Max Dotcom Chat Users", df['dotcom_chat_users'].max())
        st.metric("Max PR Users", df['pr_users'].max())

def create_timeseries_chart(df, metric, title):
    """Create a time series chart for a specific metric"""
    fig = px.line(df, x='date', y=metric, title=title)
    fig.update_xaxes(title_text='Date')
    fig.update_yaxes(title_text=metric.replace('_', ' ').title())
    return fig

def create_language_usage_chart(data):
    """Create a chart showing language usage over time"""
    language_columns = [col for col in data.columns if col not in [
        'date', 'ide_chat_users', 'code_completion_users', 'dotcom_chat_users', 
        'pr_users', 'total_active_users', 'total_engaged_users'
    ] and not col.startswith('editor_')]
    
    language_data = data.melt(id_vars=['date'], value_vars=language_columns, 
                             var_name='language', value_name='users')
    
    # Filter out languages with no usage
    language_data = language_data[language_data['users'] > 0]
    
    if not language_data.empty:
        fig = px.area(language_data, x='date', y='users', color='language',
                     title='Language Usage Over Time')
        return fig
    return None

def create_editor_usage_chart(data):
    """Create a chart showing editor usage over time"""
    editor_columns = [col for col in data.columns if col.startswith('editor_')]
    
    if editor_columns:
        editor_data = data.melt(id_vars=['date'], value_vars=editor_columns, 
                               var_name='editor', value_name='users')
        
        # Clean up editor names
        editor_data['editor'] = editor_data['editor'].str.replace('editor_', '')
        
        # Filter out editors with no usage
        editor_data = editor_data[editor_data['users'] > 0]
        
        if not editor_data.empty:
            fig = px.bar(editor_data, x='date', y='users', color='editor',
                        title='Editor Usage Over Time', barmode='stack')
            return fig
    return None

def create_acceptance_rate_analysis(data):
    """Calculate and display acceptance rate analysis"""
    # This would require more detailed data than what's in the sample
    st.info("Acceptance rate analysis requires more detailed data than provided in the sample JSON.")
    return None

def display_analysis(df):
    """Display the analysis for the provided DataFrame"""
    df['date'] = pd.to_datetime(df['date'])
    
    # Display summary metrics
    st.markdown("## 📊 Summary Metrics")
    create_summary_metrics(df)
    
    # Date range selector
    st.markdown("## 📅 Date Range Selection")
    min_date = df['date'].min()
    max_date = df['date'].max()
    
    selected_dates = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(selected_dates) == 2:
        start_date, end_date = selected_dates
        filtered_df = df[(df['date'] >= pd.to_datetime(start_date)) & 
                       (df['date'] <= pd.to_datetime(end_date))]
    else:
        filtered_df = df
    
    # Time series charts
    st.markdown("## 📈 Time Series Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_timeseries_chart(filtered_df, 'total_active_users', 'Total Active Users Over Time')
        st.plotly_chart(fig, use_container_width=True)
        
        fig = create_timeseries_chart(filtered_df, 'ide_chat_users', 'IDE Chat Users Over Time')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_timeseries_chart(filtered_df, 'total_engaged_users', 'Total Engaged Users Over Time')
        st.plotly_chart(fig, use_container_width=True)
        
        fig = create_timeseries_chart(filtered_df, 'code_completion_users', 'Code Completion Users Over Time')
        st.plotly_chart(fig, use_container_width=True)
    
    # Language usage
    st.markdown("## 💻 Language Usage")
    language_fig = create_language_usage_chart(filtered_df)
    if language_fig:
        st.plotly_chart(language_fig, use_container_width=True)
    else:
        st.info("No language usage data available for the selected period.")
    
    # Editor usage
    st.markdown("## 🖥️ Editor Usage")
    editor_fig = create_editor_usage_chart(filtered_df)
    if editor_fig:
        st.plotly_chart(editor_fig, use_container_width=True)
    else:
        st.info("No editor usage data available for the selected period.")
    
    # Raw data
    st.markdown("## 📋 Raw Data")
    st.dataframe(filtered_df)
    
    # Download button for filtered data
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name="filtered_copilot_metrics.csv",
        mime="text/csv"
    )
    
    # Insights section
    st.markdown("## 🔍 Key Insights")
    
    # Calculate some insights
    max_active_day = filtered_df.loc[filtered_df['total_active_users'].idxmax()]
    max_engaged_day = filtered_df.loc[filtered_df['total_engaged_users'].idxmax()]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Peak Usage")
        st.write(f"**Highest active users**: {max_active_day['total_active_users']} on {max_active_day['date'].strftime('%Y-%m-%d')}")
        st.write(f"**Highest engaged users**: {max_engaged_day['total_engaged_users']} on {max_engaged_day['date'].strftime('%Y-%m-%d')}")
    
    with col2:
        st.markdown("### Usage Patterns")
        avg_active = filtered_df['total_active_users'].mean()
        avg_engaged = filtered_df['total_engaged_users'].mean()
        engagement_rate = (avg_engaged / avg_active * 100) if avg_active > 0 else 0
        
        st.write(f"**Average active users**: {avg_active:.1f}")
        st.write(f"**Average engaged users**: {avg_engaged:.1f}")
        st.write(f"**Engagement rate**: {engagement_rate:.1f}%")

def main():
    st.markdown('<h1 class="main-header">GitHub Copilot Metrics Dashboard</h1>', unsafe_allow_html=True)
    
    # Create tabs for different data sources
    tab1, tab2 = st.tabs(["📁 Upload JSON File", "🌐 Fetch from GitHub API"])
    
    with tab1:
        # File upload
        uploaded_file = st.file_uploader("Upload Copilot Metrics JSON File", type="json", key="file_uploader")
        
        if uploaded_file is not None:
            # Load and process data
            raw_data = load_data(uploaded_file)
            
            if raw_data:
                df = flatten_data(raw_data)
                display_analysis(df)
            else:
                st.error("Failed to process the uploaded file. Please check the format.")
        else:
            st.info("Please upload a Copilot metrics JSON file to begin analysis.")
            
            # Show sample data structure
            # st.markdown("### Expected JSON Structure")
            # st.json({
            #     "date": "YYYY-MM-DD",
            #     "copilot_ide_chat": {
            #         "total_engaged_users": 0,
            #         "editors": [
            #             {
            #                 "name": "editor_name",
            #                 "models": [
            #                     {
            #                         "name": "model_name",
            #                         "total_chats": 0,
            #                         "is_custom_model": False,
            #                         "total_engaged_users": 0
            #                     }
            #                 ],
            #                 "total_engaged_users": 0
            #             }
            #         ]
            #     },
            #     "total_active_users": 0,
            #     "copilot_dotcom_chat": {
            #         "total_engaged_users": 0
            #     },
            #     "total_engaged_users": 0,
            #     "copilot_dotcom_pull_requests": {
            #         "total_engaged_users": 0
            #     },
            #     "copilot_ide_code_completions": {
            #         "total_engaged_users": 0,
            #         "editors": [
            #             {
            #                 "name": "editor_name",
            #                 "models": [
            #                     {
            #                         "name": "model_name",
            #                         "languages": [
            #                             {
            #                                 "name": "language_name",
            #                                 "total_engaged_users": 0,
            #                                 "total_code_acceptances": 0,
            #                                 "total_code_suggestions": 0
            #                             }
            #                         ],
            #                         "is_custom_model": False,
            #                         "total_engaged_users": 0
            #                     }
            #                 ],
            #                 "total_engaged_users": 0
            #             }
            #         ],
            #         "languages": [
            #             {
            #                 "name": "language_name",
            #                 "total_engaged_users": 0
            #             }
            #         ]
            #     }
            # })
    
    with tab2:
        st.markdown("### Fetch Data from GitHub API")
        
        # Input for GitHub API token
        api_token = st.text_input("GitHub API Token", type="password", 
                                 help="Enter a GitHub personal access token with the copilot scope")
        
        # Organization name input (optional)
        org_name = st.text_input("Organization Name (optional)", value="reizendai",
                                help="Defaults to 'reizendai'. Change if you want to fetch data for a different organization.")
        
        # Date range selection
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.now())
        
        # Fetch data button
        if st.button("Fetch Data from GitHub API", type="primary"):
            if not api_token:
                st.error("Please enter a GitHub API token.")
            elif start_date > end_date:
                st.error("Start date must be before end date.")
            else:
                with st.spinner("Fetching data from GitHub API..."):
                    raw_data = fetch_github_copilot_data(api_token, start_date, end_date, org_name)
                    
                    if raw_data:
                        st.success("Data fetched successfully!")
                        df = flatten_data(raw_data)
                        
                        # Display the data
                        display_analysis(df)
                        
                        # Option to download the fetched data
                        json_data = json.dumps(raw_data, indent=2)
                        st.download_button(
                            label="Download JSON data",
                            data=json_data,
                            file_name=f"copilot_metrics-from-{start_date}-to-{end_date}.json",
                            mime="application/json"
                        )
                    else:
                        st.error("Failed to fetch data from GitHub API. Please check your token and try again.")

if __name__ == "__main__":
    main()
