# app.py
from flask import Flask, render_template, jsonify, request, redirect, url_for
from bs4 import BeautifulSoup
import requests
import sqlite3
from datetime import datetime
import schedule
import time
import threading
import re
from urllib.parse import urljoin
import logging
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs
        (id TEXT PRIMARY KEY,
         title TEXT,
         company TEXT,
         location TEXT,
         posted_date TEXT,
         url TEXT,
         source TEXT,
         timestamp TEXT)
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_jobs
        (job_id TEXT PRIMARY KEY,
         FOREIGN KEY(job_id) REFERENCES jobs(id))
    ''')
    conn.commit()
    conn.close()

# Job scraper class
class JobScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
    def is_tech_job(self, title):
        tech_keywords = [
            'software', 'developer', 'engineer', 'it ', 'cyber', 'data',
            'web', 'python', 'java', 'javascript', 'analyst', 'devops',
            'cloud', 'security', 'frontend', 'backend', 'full stack'
        ]
        return any(keyword in title.lower() for keyword in tech_keywords)

    def load_test_data(self):
        """Load test job listings for development"""
        test_jobs = [
            {
                'id': f"test_1",
                'title': "Part-time Python Developer",
                'company': "TechCorp",
                'location': "Remote",
                'posted_date': "1 day ago",
                'url': "https://example.com/job1",
                'source': "Test Data"
            },
            {
                'id': f"test_2",
                'title': "Remote Frontend Engineer (Part-time)",
                'company': "WebStack Inc",
                'location': "Remote",
                'posted_date': "2 days ago",
                'url': "https://example.com/job2",
                'source': "Test Data"
            },
            {
                'id': f"test_3",
                'title': "Part-time Data Analyst",
                'company': "DataCo",
                'location': "Remote",
                'posted_date': "3 days ago",
                'url': "https://example.com/job3",
                'source': "Test Data"
            }
        ]
        return test_jobs
    
    def scrape_indeed(self):
        jobs = []
        url = 'https://www.indeed.com/jobs?q=remote+part+time+tech&l=Remote'
        
        try:
            logging.info(f"Attempting to scrape Indeed: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            logging.debug(f"Indeed response status: {response.status_code}")
            logging.debug(f"Indeed response headers: {response.headers}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            logging.info(f"Found {len(job_cards)} job cards on Indeed")
            
            for job in job_cards:
                title = job.find('h2', class_='jobTitle')
                if title and self.is_tech_job(title.text):
                    company = job.find('span', class_='companyName')
                    date = job.find('span', class_='date')
                    job_url = urljoin('https://www.indeed.com', 
                                    job.find('a')['href'])
                    
                    jobs.append({
                        'id': f"indeed_{hash(job_url)}",
                        'title': title.text.strip(),
                        'company': company.text.strip() if company else 'Unknown',
                        'location': 'Remote',
                        'posted_date': date.text.strip() if date else 'Unknown',
                        'url': job_url,
                        'source': 'Indeed'
                    })
        except Exception as e:
            logging.error(f"Error scraping Indeed: {str(e)}")
            logging.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            
        return jobs
    
    def scrape_weworkremotely(self):
        jobs = []
        url = 'https://weworkremotely.com/categories/remote-programming-jobs'
        
        try:
            logging.info(f"Attempting to scrape WeWorkRemotely: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            logging.debug(f"WWR response status: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            job_listings = soup.find_all('li', class_='feature')
            logging.info(f"Found {len(job_listings)} job listings on WWR")
            
            for job in job_listings:
                title = job.find('span', class_='title')
                if title and self.is_tech_job(title.text):
                    company = job.find('span', class_='company')
                    date = job.find('time')
                    job_url = urljoin('https://weworkremotely.com', 
                                    job.find('a')['href'])
                    
                    jobs.append({
                        'id': f"wwr_{hash(job_url)}",
                        'title': title.text.strip(),
                        'company': company.text.strip() if company else 'Unknown',
                        'location': 'Remote',
                        'posted_date': date.text.strip() if date else 'Unknown',
                        'url': job_url,
                        'source': 'WeWorkRemotely'
                    })
        except Exception as e:
            logging.error(f"Error scraping WeWorkRemotely: {str(e)}")
            logging.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            
        return jobs

# Job database operations
class JobDatabase:
    def __init__(self, db_path='jobs.db'):
        self.db_path = db_path
        
    def save_jobs(self, jobs):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for job in jobs:
            try:
                c.execute('''
                    INSERT OR REPLACE INTO jobs
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job['id'], job['title'], job['company'],
                    job['location'], job['posted_date'], job['url'],
                    job['source'], datetime.now().isoformat()
                ))
            except sqlite3.Error as e:
                logging.error(f"Database error: {str(e)}")
                
        conn.commit()
        conn.close()
        
    def get_jobs(self, limit=50):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                SELECT j.*, 
                       CASE WHEN sj.job_id IS NOT NULL THEN 1 ELSE 0 END as saved
                FROM jobs j
                LEFT JOIN saved_jobs sj ON j.id = sj.job_id
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            jobs = [{
                'id': row[0],
                'title': row[1],
                'company': row[2],
                'location': row[3],
                'posted_date': row[4],
                'url': row[5],
                'source': row[6],
                'timestamp': row[7],
                'saved': bool(row[8])
            } for row in c.fetchall()]
            
            logging.info(f"Retrieved {len(jobs)} jobs from database")
            return jobs
            
        except sqlite3.Error as e:
            logging.error(f"Error retrieving jobs: {str(e)}")
            return []
        finally:
            conn.close()
        
    def save_job_bookmark(self, job_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('INSERT INTO saved_jobs VALUES (?)', (job_id,))
            conn.commit()
            logging.info(f"Saved bookmark for job {job_id}")
        except sqlite3.Error as e:
            logging.error(f"Error saving bookmark: {str(e)}")
            
        conn.close()
        
    def remove_job_bookmark(self, job_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('DELETE FROM saved_jobs WHERE job_id = ?', (job_id,))
            conn.commit()
            logging.info(f"Removed bookmark for job {job_id}")
        except sqlite3.Error as e:
            logging.error(f"Error removing bookmark: {str(e)}")
            
        conn.close()

# Initialize components
init_db()
job_scraper = JobScraper()
job_db = JobDatabase()

# Scheduled job scraping
def scrape_all_jobs():
    logging.info("Starting scheduled job scraping")
    jobs = []
    jobs.extend(job_scraper.scrape_indeed())
    jobs.extend(job_scraper.scrape_weworkremotely())
    
    # If no jobs were found from scraping, load test data
    if not jobs:
        logging.warning("No jobs found from scraping, loading test data")
        jobs = job_scraper.load_test_data()
    
    job_db.save_jobs(jobs)
    logging.info(f"Saved {len(jobs)} jobs to database")

def run_scheduler():
    schedule.every(6).hours.do(scrape_all_jobs)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler in background thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Flask routes
@app.route('/')
def index():
    jobs = job_db.get_jobs()
    return render_template('index.html', jobs=jobs)

@app.route('/save_job/<job_id>', methods=['POST'])
def save_job(job_id):
    job_db.save_job_bookmark(job_id)
    return jsonify({'status': 'success'})

@app.route('/unsave_job/<job_id>', methods=['POST'])
def unsave_job(job_id):
    job_db.remove_job_bookmark(job_id)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # Initial scrape
    scrape_all_jobs()
    app.run(debug=True)