# -*- coding: utf-8 -*-

import argparse
import random
import datetime
import argparse
import requests
import pandas as pd
import fitz
import re
import sys
import os
import sqlite3
from PyPDF2 import PdfReader
#import assignment0

def save_pdf_from_url(download_url, filename='incident.pdf'):
    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()  # Will raise an HTTPError for certain status codes

        with open(filename, 'wb') as pdf_file:
            for chunk in response.iter_content(chunk_size=8192): 
                if chunk:  # Filter out keep-alive new chunks
                    pdf_file.write(chunk)
        return filename
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error occurred: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error downloading the file: {e}")
        return None
    

def download_pdfs_from_csv(csv_filepath):
    with open(csv_filepath, newline='') as csvfile:
        url_reader = csv.reader(csvfile)
        for row in url_reader:
            url = row[0]  # Assuming each line contains one URL
            # Construct a meaningful filename from the URL or use a default with an index
            # For simplicity, here we just use the URL's last part after splitting by '/'
            # and prepend a directory name where files will be saved.
            filename = os.path.join("downloaded_pdfs", url.split('/')[-1])
            if not os.path.exists("downloaded_pdfs"):
                os.makedirs("downloaded_pdfs")
            result = save_pdf_from_url(url, filename)
            if result:
                print(f"Downloaded {url} as {filename}")
            else:
                print(f"Failed to download {url}")

                

def parse_pdf_for_incidents(file_path):
    """
    Parses a PDF file to extract incident information.

    Parameters:
    :param file_path: Path to the PDF file containing incident data.

    Returns:
    :return: A list of dictionaries, each containing details about an incident.
    """
    try:
        pdf_document = fitz.open(file_path)
    except fitz.FileDataError as e:
        print(f"Error opening file: {e}")
        return []  # Return an empty list if the file cannot be opened

    combined_text = ""
    for page in pdf_document:
        combined_text += page.get_text()
    pdf_document.close()

    text_lines = combined_text.split('\n')

    incidents_list = []

    for line_index in range(len(text_lines)):
        if 'Date / Time' in text_lines[line_index]:
            continue  # Skip the header line

        if line_index + 4 < len(text_lines) and '/' in text_lines[line_index] and ':' in text_lines[line_index]:
            incident_record = {
                'Date/Time': text_lines[line_index].strip(),
                'Incident Number': text_lines[line_index + 1].strip(),
                'Location': text_lines[line_index + 2].strip(),
                'Nature': text_lines[line_index + 3].strip(),
                'Incident ORI': text_lines[line_index + 4].strip()
            }
            incidents_list.append(incident_record)

    return incidents_list

def initialize_database():
    """
    Initializes the database within the 'Resources' folder located one level above the current directory
    and creates an 'incidents' table if it does not exist.
    The 'incident_number' column is set to be unique to avoid duplicate entries.

    Returns:
    :return: Connection object to the SQLite database.
    """
    # Navigate one level up from the current directory and create the 'Resources' directory
    parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))  # Get the parent directory
    resources_folder = os.path.join(parent_directory, 'Resources')  # Path to the resources folder outside the current folder
    
    if not os.path.exists(resources_folder):
        os.makedirs(resources_folder)

    db_path = os.path.join(resources_folder, 'normanpd.db')
    db_connection = sqlite3.connect(db_path)
    db_cursor = db_connection.cursor()
    
    db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (incident_time TEXT, incident_number TEXT UNIQUE, incident_location TEXT, nature TEXT, incident_ori TEXT)''')
    
    return db_connection

def populate_database(connection, incident_records):
    """
    Inserts unique incident records into the database. Checks if an incident number already exists to avoid duplicates.

    Parameters:
    :param connection: SQLite database connection object.
    :param incident_records: List of dictionaries, each representing an incident's details.
    """
    db_cursor = connection.cursor()
    for incident in incident_records:
        # Verify if the incident number is already in the database to maintain uniqueness
        db_cursor.execute('SELECT incident_number FROM incidents WHERE incident_number = ?', (incident['Incident Number'],))
        
        if db_cursor.fetchone() is None:
            # Insert new incident record into the database
            db_cursor.execute('INSERT INTO incidents (incident_time, incident_number, incident_location, nature, incident_ori) VALUES (?, ?, ?, ?, ?)',
                              (incident['Date/Time'], incident['Incident Number'], incident['Location'], incident['Nature'], incident['Incident ORI']))

    connection.commit()


def display_incident_statistics(database_connection):
    """
    Fetches and displays the count of incidents grouped by their nature. The results are sorted by the count in descending order
    to show the most common incidents first, and then by nature in ascending order to alphabetically organize incidents with the same count.

    Parameters:
    :param database_connection: SQLite database connection object.
    """
    cursor = database_connection.cursor()
    # Ensure the SQL command is one statement and does not contain any extra semicolons.
    incident_count_query = '''
        SELECT nature, COUNT(nature) AS cnt
        FROM incidents
        GROUP BY nature
        ORDER BY cnt DESC, nature ASC
    '''
    cursor.execute(incident_count_query)
    incident_counts = cursor.fetchall()

    for nature, count in incident_counts:
        print(f'{nature}|{count}')


def display_total_incident_count(database_path):
    """
    Opens a connection to the specified SQLite database, counts the total number of incidents recorded,
    prints the count, and then closes the database connection.

    Parameters:
    :param database_path: Path to the SQLite database file.
    """
    database_connection = sqlite3.connect(database_path)
    database_cursor = database_connection.cursor()

    total_incidents_query = 'SELECT COUNT(*) FROM incidents;'
    database_cursor.execute(total_incidents_query)
    total_count = database_cursor.fetchone()[0]  # Retrieve the total count of incidents

    print(f'Total incidents in database: {total_count}')

    database_connection.close()



def main(pdf_url):
    """
    Main function to orchestrate the download, processing, and database operations for police incident PDFs.

    Parameters:
    :param pdf_url: URL of the PDF file containing police incident data.
    """
    # Navigate one level up from the current directory to find the 'Resources' directory
    parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    resources_folder = os.path.join(parent_directory, 'Resources')
    database_file = os.path.join(resources_folder, 'normanpd.db')

    # Remove the existing database file if it exists to start fresh
    if os.path.exists(database_file):
        os.remove(database_file)

    # Download the PDF from the provided URL
    pdf_file_path = save_pdf_from_url(pdf_url)
    if not pdf_file_path:
        print("Failed to download the PDF file.")
        return  # Exit if the PDF download failed
    
    # Extract incident data from the downloaded PDF
    incident_data = parse_pdf_for_incidents(pdf_file_path)
    if not incident_data:
        print("Failed to parse the PDF file.")
        return  # Exit if the PDF parsing failed
    
    # Initialize the database and create the table if not exists, inside the Resources folder
    db_connection = initialize_database()
    
    # Populate the database with the extracted incident data
    populate_database(db_connection, incident_data)
    
    # Display the count of incidents grouped by nature
    display_incident_statistics(db_connection)
    
    # Optionally, display the total count of incidents
    # display_total_incident_count(database_file)
    
    # Clean up by removing the downloaded PDF file
    os.remove(pdf_file_path)
    
    # Close the database connection
    db_connection.close()

if _name_ == '_main_':
    parser = argparse.ArgumentParser(
        description="Process incident data from PDF URLs listed in a file.")
    parser.add_argument("--urls", type=str, required=True,
                        help="Filename containing the list of PDF URLs.")

    args = parser.parse_args()
    
    main(args.urls)
