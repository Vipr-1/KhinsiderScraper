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