#!/usr/bin/env python3

import os
import re
import sys
import cloudscraper
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
import time


# class that contains data and methods for scraping
class Scraper:
	def __init__(self, albumURI, outputDIR, audioFormat):
		self.albumURI = albumURI
		self.outputDIR = Path(outputDIR)
		self.audioFormat = audioFormat
		self.session = cloudscraper.create_scraper #set up information for the 'web agent'
		self.session.headers.update({ #define the scraper's user agent
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
		})
	
	# removes the characters frome the file name that are not allowed
	def cleanFileName(self, filename):
		return re.sub(r'[<>:"/\\|?*]', '', filename)

	def getAlbumInfo(self):
		try:
			response = self.session.get(self.albumURI, timeout = 10)
			response.raise_for_status()
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


		#Khinsider does not have downloads directly on
		#the album page, it has links to "song pages"
		#these pages have the downloads, this function grabs
		#the song pages.
	def extractSongPageLinks(self, soup):
		pageLinks = []

			#songs are in tables with the id "songlist"
			#return the empty list if the table is not found
		songTable = soup.find('table', id='songlist')
		if not songTable:
			return songTable

		for row in songTable.find_all('tr')[1:]:
			link = row.find('a')
				#If the anchor tag and the reference for it exist then proceed
			if link and link.get('href'):
				href = link.get('href')
				fullURI = urljoin(self.albumURI, href)
					#khinsider often has multiple links in the table to the
					#same page, skip duplicates
				if fullURI not in pageLinks:
					pageLinks.append(fullURI)

		return pageLinks
	
	def extractDownloadLink(self, songPageURI):
		try: 
			response = self.session.get(songPageURI, timeout=10)
			response.raise_for_status()
		except requests.RequestException as e:
			print(f"Error fetching song page: {e}")
			return None
		
		soup = BeautifulSoup(response.content, 'html.parser')
		for link in soup.find_all('a'):
			href = link.get('href', '')
			text = link.get_text(strip=True)

			if self.audioFormat in text.lower() and href.startswith('http'):
				#unquote replaces codes like %20 (spaces in URIs) with their normal counterparts
				filename = unquote(href.split('/')[-1])
				if not filename.endswith('.' + self.audioFormat):
					# Try to get a better filename from the page
					titleTag = soup.find('h2')
					if titleTag:
						filename = self.cleanFileName(titleTag.get_text(strip=True)) + '.' + self.audioFormat
			
				return {
					'uri': href,
					'filename': filename
				}
		return None



	def downloadFile(self, songURI, filepath, timeout=30, maxRetries=3):

		for attempt in range(maxRetries):
			try:
				response = self.session.get(songURI, timeout=timeout, stream=True)
				response.raise_for_status()

				#grab file size
				fileSize = int(response.headers.get('content-length', 0))

				#write file to disk with progress

				downloaded = 0
				with open(filepath, 'wb') as songFile:
					for chunk in response.iter_content(chunk_size=8192):
						if chunk:
							songFile.write(chunk)
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
	
	def scrapeAndDownload(self):
		print(f"Scraping: {self.albumURI}")

			#get album info
		albumInfo = self.getAlbumInfo()
		if not albumInfo:
			print("Failed to retrieve album information")
			return False

		print(f"Album: {albumInfo['title']}")

			#get the links to the song pages
		songPageLinks = self.extractSongPageLinks(albumInfo['soup'])
		if not songPageLinks:
			print("No song pages were found")
			return False
		print(f"Found {len(songPageLinks)} songs")

			#get actual download links
		musicLinks = []
		for songNum, songPageURI in enumerate(songPageLinks, 1):
			print(f"Checking song {songNum}/{len(songPageLinks)}...", end='\r')
			musicLink = self.extractDownloadLink(songPageURI)
			if musicLink:
				musicLinks.append(musicLink)
			time.sleep(0.5)  # Be respectful to the server

		print(f"\nFound {len(musicLinks)} {self.audioFormat} files")
    
		if not musicLinks:
			print(f"No {self.audioFormat} downloads were found")
			return False



		
		print(f"Found {len(musicLinks)} {self.audioFormat} files")

			#make the album directory
		albumDIR = self.outputDIR / albumInfo['title']
		try:
			albumDIR.mkdir(parents=True, exist_ok=True)
		except Exception as e:
			print(f"Error Creating directory {albumDIR}: {e}")
			return False
		
			#download the files
		successfullDownloads = 0
		for songNum, songLink, in enumerate(musicLinks, 1):
			filename = self.cleanFileName(songLink['filename'])
			filepath = albumDIR / filename

			print(f"\n[{songNum}/{len(musicLinks)}] Downloading: {filename}")

			#skip file if already there
			if filepath.exists():
				print(f"	File already exists, skipping")
				successfullDownloads += 1
				continue

			#download the file
			if self.downloadFile(songLink['uri'], filepath):
				successfullDownloads += 1
				continue

			# rate limit to avoid server isssues
			if songNum < len(musicLinks):
				time.sleep(1)
			

		print(f"\n\nDownlaod complete: {successfullDownloads}/{len(musicLinks)} files downloaded")
		return successfullDownloads == len(musicLinks)

	
def main():
	if len(sys.argv) < 2:
		print("Usage: ./scraper.py <album_URI> [audio_format] [output_directory]")
		sys.exit(1)
	
	albumURI = sys.argv[1]
		#use flac as the default file format
	audioFormat = sys.argv[2] if len(sys.argv) > 2 else "flac"
		#Unix user downloads folder is the default
	outputDIR = sys.argv[3] if len(sys.argv) > 3 else "~/Downloads"
	outputDIR = Path(outputDIR).expanduser()

	scraper = Scraper(albumURI, outputDIR, audioFormat)
	success = scraper.scrapeAndDownload()

	sys.exit(0 if success else 1)


	#run only if not imported
if __name__ == "__main__":
	main()
