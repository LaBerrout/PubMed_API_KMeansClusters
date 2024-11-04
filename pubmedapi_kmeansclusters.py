# -*- coding: utf-8 -*-
"""PubMedAPI_Modifications_Version.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1-du2GrJ8wrbzeJpbHB_peScnfw7GVCW-
"""

pip install biopython

pip install pandas scikit-learn nltk

import csv
import pandas as pd
import re
from Bio import Entrez
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
#from nltk.corpus import stopwords
import nltk
import os

# Set your email (required by NCBI)
Entrez.email = "laberroutra@utep.edu"

# Define search term and keywords
keywords = ["diabetes", "prediabetes","diabetic","prediabetic"]
#search_term = " (inflammation OR biomarker) AND  ".join(keywords)  # This will search for articles containing any of the keywords
search_term = " (hispanic OR latino OR latina OR latinx) AND ".join(keywords)


# Pagination variables
retmax = 1000  # Number of results per batch
retstart = 0   # Start index

# Initialize empty list for PubMed IDs
pubmed_ids = []

# Fetch all PubMed IDs in batches
while True:
    search_handle = Entrez.esearch(
        db="pubmed",
        term=search_term,
        retmax=retmax,
        retstart=retstart,
        mindate="2014",
        maxdate="2024",
        datetype="pdat"
    )
    search_results = Entrez.read(search_handle)
    search_handle.close()

    # Add the retrieved IDs to the list
    pubmed_ids.extend(search_results["IdList"])

    # Check if we've retrieved all available results
    if len(search_results["IdList"]) < retmax:
        break
    else:
        retstart += retmax

# Create a list to store the data
data = []

if pubmed_ids:
    # Fetch articles in chunks of 1000 IDs to avoid overwhelming the API
    for i in range(0, len(pubmed_ids), 1000):
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(pubmed_ids[i:i+1000]), retmode="xml")
        fetch_results = Entrez.read(fetch_handle)
        fetch_handle.close()

        # Loop through each article and extract details
        for article in fetch_results['PubmedArticle']:
            # Extract title
            title = article['MedlineCitation']['Article']['ArticleTitle']

            # Extract abstract (or handle cases where no abstract is available)
            abstract = article['MedlineCitation']['Article'].get('Abstract', {}).get('AbstractText', ['No abstract available'])[0]

            # Extract journal info
            journal = article['MedlineCitation']['Article']['Journal']['Title']

            # Extract the year of publishing
            pub_date = article['MedlineCitation']['Article']['Journal']['JournalIssue']['PubDate']
            if 'Year' in pub_date:
                pub_date = pub_date['Year']
            else:
                pub_date = 'No year available'

            # Extract authors
            authors = []
            for author in article['MedlineCitation']['Article']['AuthorList']:
                last_name = author.get('LastName', '')
                first_name = author.get('ForeName', '')

                # Safely handle affiliation info
                affiliation_info = author.get('AffiliationInfo', [])
                if affiliation_info:
                    affiliation = affiliation_info[0].get('Affiliation', 'No affiliation')
                else:
                    affiliation = 'No affiliation'

                authors.append(f"{first_name} {last_name} (Affiliation: {affiliation})")

            # Extract DOI
            doi = None
            for elink in article['PubmedData']['ArticleIdList']:
                if elink.attributes.get('IdType') == 'doi':
                    doi = elink

            # Extract MeSH Terms
            mesh_terms = []
            for mesh in article['MedlineCitation'].get('MeshHeadingList', []):
                mesh_term = mesh['DescriptorName']
                mesh_terms.append(mesh_term)

            # Extract Grant Support
            grants = []
            for grant in article['MedlineCitation']['Article'].get('GrantList', []):
                grant_agency = grant.get('Agency', 'No agency')
                grant_id = grant.get('GrantID', 'No grant ID')
                grants.append(f"{grant_agency} (Grant ID: {grant_id})")

            # Extract Keywords
            keywords_list = article['MedlineCitation']['KeywordList']
            keyword_list = []
            if keywords_list:
                keyword_list = [kw for kw in keywords_list[0]]  # PubMed often stores keywords in nested lists

            # Extract Publication Type
            pub_type_list = []
            for pub_type in article['MedlineCitation']['Article'].get('PublicationTypeList', []):
                pub_type_list.append(pub_type)

            # Extract References (if available)
            references = []
            if 'CommentsCorrectionsList' in article['MedlineCitation']:
                for ref in article['MedlineCitation']['CommentsCorrectionsList']:
                    if ref.attributes.get('RefType') == 'Cites':
                        references.append(ref['RefSource'])

            # Find which keywords are mentioned in the title and abstract
            keywords_in_title = [kw for kw in keywords if kw.lower() in title.lower()]
            keywords_in_abstract = [kw for kw in keywords if kw.lower() in abstract.lower()]

            # Append the article details to the data list
            data.append([
                title, journal, pub_date, ', '.join(authors), doi if doi else 'No DOI available', abstract,
                ', '.join(mesh_terms), ', '.join(grants), ', '.join(keyword_list),
                ', '.join(pub_type_list), ', '.join(references), ', '.join(keywords_in_title), ', '.join(keywords_in_abstract)
            ])

    # Create a DataFrame from the data list
    df = pd.DataFrame(data, columns=[
        'Title', 'Journal', 'Publication Date', 'Authors', 'DOI', 'Abstract', 'MeSH Terms', 'Grant Support',
        'Keywords', 'Publication Type', 'References', 'Keywords in Title', 'Keywords in Abstract'
    ])

    # Save the DataFrame to a CSV file
    df.to_csv('articles_list.csv', index=False)

    print("Data has been successfully written to articles_list.csv and saved in a DataFrame.")
else:
    print("No articles found for the given keywords and date range.")

print("Size of the resulting dataframe:", df.shape[0])

"""## Cleaning the data
We need to clean the data, to analyze only the papers relevant to us
"""

# From the keywords, remove the papers from the list do not mention diabetes or pre-diabetes
# List of keywords

# Filtering rows where keywords do not appear in both columns
fil_df = df[(df['Keywords in Title'] != '') | (df['Keywords in Abstract'] != '')]

print("Size of the filtered dataframe:",fil_df.shape[0])

# ***  Cleaning the columns ***
# Function to convert to lowercase and remove special characters
# List of stop words to remove
stop_words = ['a', 'of', 'the', 'is', 'in', 'on', 'at', 'for', 'and', 'to', 'this', 'we', 'et al']

# Add stop words not relevant that appears in the clusters
more_stop_words = ['aimed', 'relevant', 'available', 'risk', 'study', 'studies','patients', 'disease',
                   'people', 'association', 'type', 'abstract','levels', 'diabetes', 'diabetic','prediabetes',
                   'investigate','vs','associated','individuals','subjects','group', 'resistance', 'effects', 'prediabetic',
                   'biomarkers', 'control', 'diseases', 'increased', 'outcomes', 'clinical', 'mortality', 'factors',
                   'development', 'clinical', 'expression', 'metabolic', 'prediabetic', 'biomarkers','early',
                   'women']
for i in range(len(more_stop_words)):
    stop_words.append(more_stop_words[i])

# Remove special characters and filler words, and lower case
def clean_string_remove_fillers(s):
    # Remove special characters and lower case
    s_cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', s).lower()

    # Remove filler words
    words = s_cleaned.split()  # Split sentence into words
    return ' '.join([word for word in words if word not in stop_words])  # Remove filler words

#Clean title and abstract columns: Apply function to remove filler, special characters and lower case
fil_df['title_cleaned'] = fil_df['Title'].apply(clean_string_remove_fillers)
fil_df['abstract_cleaned'] = fil_df['Abstract'].apply(clean_string_remove_fillers)

# Save the filtered df to a CSV file
fil_df.to_csv('clean_list.csv', index=False)

"""# K-Mean Clustering Algorithm

Using the features:
* Title
* Abstract
* Mesh Terms (MA says, may or may not be useful to add, start without this feature)

### Apply the K-Clustering Algorithm
"""

# Change datatype to vectorize
documents = fil_df['abstract_cleaned'].values.astype("U")

# Vectorize and remove stop words
vectorizer = TfidfVectorizer(stop_words='english')
features = vectorizer.fit_transform(documents)

# Number of clusters
k = 2

# Base name for the folder
base_name = "Hispanic-"

# Create folders
folder_name = f"{base_name}{k}"
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

# Clustering
model = KMeans(n_clusters=k, init='k-means++', max_iter=100, n_init=1)
model.fit(features)

# Add cluster labels to the dataframe
fil_df['cluster'] = model.labels_

# Output the result to CSV files
clusters = fil_df.groupby('cluster')

for cluster in clusters.groups:
    # Full path where the CSV will be saved
    file_path = os.path.join(folder_name, f'cluster_{cluster}.csv')

    # Save the entire dataframe for each cluster to the CSV file
    data = clusters.get_group(cluster)  # Saves all the dataframe
    data.to_csv(file_path, index_label='id')

#print("Cluster centroids: \n")
order_centroids = model.cluster_centers_.argsort()[:, ::-1]
terms = vectorizer.get_feature_names_out()

for i in range(k):
    print("Cluster %d:" % i)
    for j in order_centroids[i, :10]:  # Print out top 10 feature terms of each cluster
        print(' %s' % terms[j])
    print('------------')

"""WordCloud

for future, use embeddings of the title and abstract (from medicalBERT or something similar) for clustering and compare how word-based approach performs against embedding-based clustering approach.
"""