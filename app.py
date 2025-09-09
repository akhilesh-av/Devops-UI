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

def extract_language_acceptance_data(data):
    """Extract detailed language acceptance data from the JSON structure"""
    language_data = []
    
    for day in data:
        date = day['date']
        editors = day.get('copilot_ide_code_completions', {}).get('editors', [])
        
        for editor in editors:
            editor_name = editor['name']
            models = editor.get('models', [])
            
            for model in models:
                languages = model.get('languages', [])
                
                for lang in languages:
                    language_data.append({
                        'date': date,
                        'editor': editor_name,
                        'language': lang['name'],
                        'total_engaged_users': lang.get('total_engaged_users', 0),
                        'total_code_acceptances': lang.get('total_code_acceptances', 0),
                        'total_code_suggestions': lang.get('total_code_suggestions', 0),
                        'total_code_lines_accepted': lang.get('total_code_lines_accepted', 0),
                        'total_code_lines_suggested': lang.get('total_code_lines_suggested', 0)
                    })
    
    return pd.DataFrame(language_data)

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

def create_individual_language_charts(language_df):
    """Create individual charts for each language showing usage over time"""
    languages = language_df['language'].unique()
    
    for language in languages:
        if language != 'unknown':  # Skip unknown language
            lang_data = language_df[language_df['language'] == language]
            
            if not lang_data.empty and lang_data['total_engaged_users'].sum() > 0:
                st.markdown(f"### {language.title()} Usage")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Users over time
                    fig = px.line(lang_data, x='date', y='total_engaged_users', 
                                 title=f'{language.title()} - Engaged Users Over Time')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Acceptance rate over time
                    lang_data['acceptance_rate'] = (lang_data['total_code_acceptances'] / 
                                                   lang_data['total_code_suggestions'] * 100)
                    lang_data['acceptance_rate'] = lang_data['acceptance_rate'].replace([np.inf, -np.inf], 0)
                    lang_data['acceptance_rate'] = lang_data['acceptance_rate'].fillna(0)
                    
                    fig = px.line(lang_data, x='date', y='acceptance_rate', 
                                 title=f'{language.title()} - Acceptance Rate Over Time')
                    fig.update_yaxes(title_text='Acceptance Rate (%)', range=[0, 100])
                    st.plotly_chart(fig, use_container_width=True)

def create_acceptance_rate_analysis(language_df):
    """Calculate and display acceptance rate analysis by language"""
    st.markdown("## 📊 Code Acceptance Rate by Language")
    
    # Calculate acceptance rates
    language_stats = language_df.groupby('language').agg({
        'total_code_acceptances': 'sum',
        'total_code_suggestions': 'sum',
        'total_code_lines_accepted': 'sum',
        'total_code_lines_suggested': 'sum',
        'total_engaged_users': 'sum'
    }).reset_index()
    
    language_stats['acceptance_rate'] = (language_stats['total_code_acceptances'] / 
                                        language_stats['total_code_suggestions'] * 100)
    language_stats['lines_acceptance_rate'] = (language_stats['total_code_lines_accepted'] / 
                                              language_stats['total_code_lines_suggested'] * 100)
    
    # Replace inf and NaN values
    language_stats['acceptance_rate'] = language_stats['acceptance_rate'].replace([np.inf, -np.inf], 0)
    language_stats['acceptance_rate'] = language_stats['acceptance_rate'].fillna(0)
    language_stats['lines_acceptance_rate'] = language_stats['lines_acceptance_rate'].replace([np.inf, -np.inf], 0)
    language_stats['lines_acceptance_rate'] = language_stats['lines_acceptance_rate'].fillna(0)
    
    # Filter out languages with no usage
    language_stats = language_stats[language_stats['total_engaged_users'] > 0]
    
    if not language_stats.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Acceptance rate by language (bar chart)
            fig = px.bar(language_stats, x='language', y='acceptance_rate',
                        title='Code Acceptance Rate by Language',
                        labels={'acceptance_rate': 'Acceptance Rate (%)', 'language': 'Language'})
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Lines acceptance rate by language
            fig = px.bar(language_stats, x='language', y='lines_acceptance_rate',
                        title='Lines Acceptance Rate by Language',
                        labels={'lines_acceptance_rate': 'Lines Acceptance Rate (%)', 'language': 'Language'})
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        # Display detailed table
        st.markdown("### Detailed Language Statistics")
        display_df = language_stats[['language', 'total_engaged_users', 'total_code_suggestions', 
                                   'total_code_acceptances', 'acceptance_rate', 
                                   'total_code_lines_suggested', 'total_code_lines_accepted', 
                                   'lines_acceptance_rate']]
        display_df = display_df.round({'acceptance_rate': 2, 'lines_acceptance_rate': 2})
        st.dataframe(display_df)
    else:
        st.info("No language usage data available for the selected period.")

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

def create_productivity_analysis(language_df):
    """Create productivity analysis based on code completion metrics"""
    st.markdown("## 🚀 Productivity Analysis")
    
    # Calculate overall productivity metrics
    total_suggestions = language_df['total_code_suggestions'].sum()
    total_acceptances = language_df['total_code_acceptances'].sum()
    total_lines_suggested = language_df['total_code_lines_suggested'].sum()
    total_lines_accepted = language_df['total_code_lines_accepted'].sum()
    
    overall_acceptance_rate = (total_acceptances / total_suggestions * 100) if total_suggestions > 0 else 0
    lines_acceptance_rate = (total_lines_accepted / total_lines_suggested * 100) if total_lines_suggested > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Suggestions", f"{total_suggestions:,}")
    
    with col2:
        st.metric("Total Acceptances", f"{total_acceptances:,}")
    
    with col3:
        st.metric("Overall Acceptance Rate", f"{overall_acceptance_rate:.1f}%")
    
    with col4:
        st.metric("Lines Acceptance Rate", f"{lines_acceptance_rate:.1f}%")
    
    # Daily productivity trends
    daily_stats = language_df.groupby('date').agg({
        'total_code_suggestions': 'sum',
        'total_code_acceptances': 'sum',
        'total_code_lines_suggested': 'sum',
        'total_code_lines_accepted': 'sum'
    }).reset_index()
    
    daily_stats['acceptance_rate'] = (daily_stats['total_code_acceptances'] / 
                                     daily_stats['total_code_suggestions'] * 100)
    daily_stats['acceptance_rate'] = daily_stats['acceptance_rate'].replace([np.inf, -np.inf], 0)
    daily_stats['acceptance_rate'] = daily_stats['acceptance_rate'].fillna(0)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.line(daily_stats, x='date', y=['total_code_suggestions', 'total_code_acceptances'],
                     title='Daily Code Suggestions and Acceptances',
                     labels={'value': 'Count', 'variable': 'Metric'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.line(daily_stats, x='date', y='acceptance_rate',
                     title='Daily Acceptance Rate Trend',
                     labels={'acceptance_rate': 'Acceptance Rate (%)'})
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

def display_analysis(df, language_df):
    """Display the analysis for the provided DataFrame"""
    df['date'] = pd.to_datetime(df['date'])
    language_df['date'] = pd.to_datetime(language_df['date'])
    
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
        filtered_language_df = language_df[(language_df['date'] >= pd.to_datetime(start_date)) & 
                                         (language_df['date'] <= pd.to_datetime(end_date))]
    else:
        filtered_df = df
        filtered_language_df = language_df
    
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
    
    # Language usage - individual charts
    st.markdown("## 💻 Language Usage (Individual Charts)")
    create_individual_language_charts(filtered_language_df)
    
    # Acceptance rate analysis
    create_acceptance_rate_analysis(filtered_language_df)
    
    # Productivity analysis
    create_productivity_analysis(filtered_language_df)
    
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
                language_df = extract_language_acceptance_data(raw_data)
                display_analysis(df, language_df)
            else:
                st.error("Failed to process the uploaded file. Please check the format.")
        else:
            st.info("Please upload a Copilot metrics JSON file to begin analysis.")
            
          
    
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
                        language_df = extract_language_acceptance_data(raw_data)
                        
                        # Display the data
                        display_analysis(df, language_df)
                        
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
