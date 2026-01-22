#!/bin/python

import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
import time


# class that contains data and methods for scraping
class Scraper:
	def __init__(self, albumURI, outputDIR):
		self.albumURI = albumURI
		self.outputDIR = Path(outputDIR)
		self.session = requests.Session() #set up information for the 'web agent'
		self.session.headers.update({ #define the scraper's user agent
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/146.0'
		})
	
	# removes the characters frome the file name that are not allowed
	def cleanFileName(self, filename):
		return re.sub(r'[<>:"/\\|?*]', '', filename)

	def getAlbumInfo(self):
		try:
			response = self.session.get(self.albumURI, timeout = 10)
			response.raiseForStatus()
		except requests.RequestException as exception:
			print(f"Error fetching album: {exception}")
			return None
		
		soup = BeautifulSoup(response.content, 'html.parser')

		#Extract album title
		titleTag = soup.find('h2')
		if titleTag:
			albumTitle = titleTag.get_text(strip=True)
		else:
			albumTitle = "Unknown Album"
		albumTitle = self.cleanFileName(albumTitle)

		return {
			'title': albumTitle,
			'soup': soup,
			'html': response.text
		}
	
	def extractDownloadLinks(self, htmlContent):
		soup = BeautifulSoup(htmlContent, 'html.parser')

		flacLinks = []

		#look for download links in all formats
		for link in soup.find_all('a'):
			href = link.get('href', '')
			text = link.get_text(strip=True).lower()

			#grab flac links
			if 'flac' in text.lower() or href.endswith('.flac'):
				if href.startswith('http'):
					flacLinks.append({
						'uri': href,
						'filename': href.split('/')[-1]
					})
		
		return flacLinks


	def downloadFile(self, songURI, filepath, timeout=30, maxRetries=3):

		for attempt in range(maxRetries):
			try:
				response = self.session.get(songURI, timeout=timeout, stream=True)
				response.raiseForStatus()

				#grab file size
				fileSize = int(response.headers.get('content-length', 0))

				#write file to disk with progress

				downloaded = 0
				with open(filepath, 'wb') as songFile:
					for chunk in response.iter_content(chunkSize=8192):
						if chunk:
							file.write(chunk)
							downloaded += len(chunk)

							#print percent complete
						if fileSize > 0:
							percentDownloaded = (downloaded / fileSize) * 100
							print(f"	Downloaded: {percentDownloaded:.1f}%", end='\r')

				print(f"	Successfully Downloaded: {filepath.name}")
				return True
			
			except requests.RequestException as e:
				print(f"	Attempt {attempt + 1}/{maxRetries} failed: {e}")
				if attempt < (maxRetries - 1):
					time.sleep(2) #wait
				continue

		print(f"	Failed to download")
		return False