
# TODO:
# - Implement OCR for full paper extraction?
# - Test!!
# - Make code more modular/readable variable names
# - Figure out ways to check accuracy without just space ratio
# - Add ability to not continue w grobid body section for abstract extraction and go straight to ocr?
# - Automate some of the setup?

# Can modify functions based on needs.. OCR most accurate but slowest, grobid faster with good accuracy.
# Assuming cloned grobid_client_python repo is in ../
from ..grobid_client_python.grobid_client.grobid_client import GrobidClient
import xml.etree.ElementTree as ET
import os, time
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import argparse

# PARAMETERS
parser = argparse.ArgumentParser(description="PDF Extractor with GROBID and OCR")
parser.add_argument('--threads', type=int, default=10, help='Number of threads to use for grobid, default to 10')
parser.add_argument('--pdffilepath', type=str, default="Conference Papers", help='Path to PDF file folder to extract abstract from')
parser.add_argument('--fullpaper', action='store_true', help='Whether to extract full papers or just abstracts')
args = parser.parse_args()

# Assign args values
threads = args.threads
pdffilepath = args.pdffilepath
fullpaper = args.fullpaper

# Default directory names
output_path = "./grobid_output/" # grobid output directory
text_directory = './paper_abstracts/' # directory to contain the txt files
empty_abstract_file = 'grobid_fail.txt' # file to save the names of the files where grobid fails
imagedir = './ocrimages/' # directory to contain OCR images
ocrtextdir = './ocrtexts/' # directory to contain OCR text extractions

corrupt_papers = []
problem_papers = []
maybe_problem_papers = []

class ServerUnavailableException(Exception):
    pass

def checkSpaceRatio(s): # not perfect, choose ratio threshhold carefully. Simply checking space ratio may not be the best solution to bad output.
    space_count = s.count(' ')
    return space_count / len(s) < 0.3

def createDir(path):
    if not os.path.isdir(path):
        try:
            print("Directory does not exist but will be created:", path)
            os.makedirs(path)
        except OSError:
            print("Creation of the directory", path, "failed")
        else:
            print("Successfully created the directory", path)

def grobidExtract():
    if not os.path.isdir(pdffilepath):
        print("PDF folder not found at path:", pdffilepath)
        exit(1)
    createDir(output_path)
    try:    
        client = GrobidClient(config_path="../grobid_client_python/config.json")
    except ServerUnavailableException:
        print("GROBID server is not available")
        exit(1)
    
    start_time = time.time()
    # Does not force reprocessing if xml already exists. Verbose mode is turned off
    client.process("processFulltextDocument", pdffilepath, output=output_path, n=threads, force=False)
    runtime = round((time.time() - start_time), 3)
    print("GROBID runtime: %s seconds " % (runtime))
    if fullpaper:
        grobidFullExtract(output_path)
    else:
        grobidAbsExtract(output_path)

def grobidAbsExtract(output_path):
    xml_directory = output_path
    createDir(text_directory)
    print("Attempting abstract extraction...")
    abscount = 0
    noabscnt = 0
    corruptcnt = 0
    found_abstract = False
    with open(empty_abstract_file, 'w', encoding='utf-8') as empty_abstract_f:
        # Iterate over all XML files in the grobid output directory
            for filename in os.listdir(xml_directory):
                # Parse the XML file
                if filename.endswith('.grobid.tei.xml'):
                    tree = ET.parse(os.path.join(xml_directory, filename))
                    root = tree.getroot()
                    # Find the abstract element
                    abstract = root.find(".//{http://www.tei-c.org/ns/1.0}teiHeader").find(".//{http://www.tei-c.org/ns/1.0}profileDesc").find(".//{http://www.tei-c.org/ns/1.0}abstract")
                    abstractp = abstract.find(".//{http://www.tei-c.org/ns/1.0}p")
                    if abstractp is not None:
                        # can check length and space ratio in this block if you find that it's needed
                        abstractp = abstractp.text.strip()
                        with open(os.path.join(text_directory, filename.replace('.grobid.tei.xml', '.txt')), 'w', encoding='utf-8') as f:
                            f.write(abstractp)
                        abscount += 1
                        continue
                    # Sometimes grobid splits into multiple paragraphs:
                    abstract = abstract.find(".//{http://www.tei-c.org/ns/1.0}div")
                    abstracttext = ''
                    if abstract is not None:
                        paragraphs = abstract.findall(".//{http://www.tei-c.org/ns/1.0}p")
                        for p in paragraphs:
                            abstracttext += ''.join(p.itertext())
                        if len(abstracttext) >= 300 and checkSpaceRatio(abstracttext):
                            with open(os.path.join(text_directory, filename.replace('.grobid.tei.xml', '.txt')), 'w', encoding='utf-8') as f:
                                f.write(abstracttext)
                            abscount += 1
                            continue
                    # From here is attempting to extract from some body section of grobid output since abstract not recognized by header model.
                    # We extract text cummulatively until we get a good length and space ratio. Could add an option to either try "body" extraction first
                    # or just go straight to OCR extraction. Adds on to anything stored in abstracttext from above. May not be optimal solution 
                    # (some small parts of the output can be bad and might slip through).

                    # For each body div, pull and append all text and check if requirements satisfied
                    # MAYBE DELETE THIS as it may be less accurate than OCR?
                    abstracts = root.find(".//{http://www.tei-c.org/ns/1.0}text").find(".//{http://www.tei-c.org/ns/1.0}body").findall(".//{http://www.tei-c.org/ns/1.0}div")
                    i = 0
                    while i < len(abstracts):
                        abstract = abstracts[i]
                        i += 1
                        paragraphs = abstract.findall(".//{http://www.tei-c.org/ns/1.0}p")
                        for p in paragraphs:
                            abstracttext += ''.join(p.itertext())
                        if len(abstracttext) >= 300 and checkSpaceRatio(abstracttext):
                            with open(os.path.join(text_directory, filename.replace('.grobid.tei.xml', '.txt')), 'w', encoding='utf-8') as f:
                                f.write(abstracttext)
                            abscount += 1
                            found_abstract = True
                            break
                    
                    if found_abstract:
                        found_abstract = False
                        continue
                    noabscnt += 1
                    empty_abstract_f.write(filename.replace('.grobid.tei.xml', '.pdf') + '\n')
                else:
                    corrupt_papers.append(filename.replace('.txt', '.pdf'))
                    corruptcnt += 1

    print("Extracted: "+ abscount)
    print("GROBID Failed: " + noabscnt)
    print("Corrupt files: " + corruptcnt)
    print("Total papers: " + (noabscnt + abscount + corruptcnt))
    if noabscnt > 0:
        ocrExtract(empty_abstract_file)
    print("Corrupt papers: ", corrupt_papers)
    print("Failed extraction: ", problem_papers)
    print("Maybe problem papers: ", maybe_problem_papers)

def grobidFullExtract(output_path):
    xml_directory = output_path
    createDir(text_directory)
    print("Attempting full text extraction...")
    abscount = 0
    noabscnt = 0
    corruptcnt = 0
    with open(empty_abstract_file, 'w', encoding='utf-8') as extractfailfile:
        # Iterate over all XML files in the grobid output directory
            for filename in os.listdir(xml_directory):
                # Parse the XML file
                if filename.endswith('.grobid.tei.xml'):
                    tree = ET.parse(os.path.join(xml_directory, filename))
                    root = tree.getroot()
                    abstracttext = ''
                    # Find the abstract element
                    abstract = root.find(".//{http://www.tei-c.org/ns/1.0}teiHeader").find(".//{http://www.tei-c.org/ns/1.0}profileDesc").find(".//{http://www.tei-c.org/ns/1.0}abstract")
                    abstractp = abstract.find(".//{http://www.tei-c.org/ns/1.0}p")
                    if abstractp is not None:
                        # can check length and space ratio in this block if you find that it's needed
                        abstractp = abstractp.text.strip()
                        abstracttext += abstractp
                    else:
                        abstract = abstract.find(".//{http://www.tei-c.org/ns/1.0}div")
                        if abstract is not None:
                            paragraphs = abstract.findall(".//{http://www.tei-c.org/ns/1.0}p")
                            for p in paragraphs:
                                abstracttext += ''.join(p.itertext())
                    abstracttext += '\n\n'
                else:
                    corrupt_papers.append(filename.replace('.txt', '.pdf'))
                    corruptcnt += 1
                
                if checkSpaceRatio(abstracttext):
                    success = continueFullExtract(abstracttext, filename, root)
                    if success:
                        abscount += 1
                    else:
                        noabscnt += 1
                else: # If the space ratio of the abstract is bad, defer to ocr (not yet implemented). Otherwise extract the rest of the paper
                    extractfailfile.write(filename.replace('.grobid.tei.xml', '.pdf') + '\n')
                    noabscnt += 1

    print("Extracted: "+ abscount)
    print("GROBID Failed: " + noabscnt)
    print("See grobidfails.txt for list of failed papers.")
    print("Corrupt files: " + corruptcnt)
    print("Total papers: " + (noabscnt + abscount + corruptcnt))
    # ADD SUPPORT FOR FULL PAPER OCR EXTRACTION IN A FUNCTION CALL HERE
    # if noabscnt > 0:
    #     ocrFullExtract(empty_abstract_file)
    print("Corrupt papers: ", corrupt_papers)
    # print("Failed extraction: ", problem_papers)
    # print("Maybe problem papers: ", maybe_problem_papers)

# Fix variable names. Need a way to check accuracy
def continueFullExtract(abstracttext, filename, root):
    abstracts = root.find(".//{http://www.tei-c.org/ns/1.0}text").find(".//{http://www.tei-c.org/ns/1.0}body").findall(".//{http://www.tei-c.org/ns/1.0}div")
    i = 0
    while i < len(abstracts):
        abstract = abstracts[i]
        i += 1
        paragraphs = abstract.findall(".//{http://www.tei-c.org/ns/1.0}p")
        for p in paragraphs:
            abstracttext += ''.join(p.itertext())
            abstracttext += '\n'
        abstracttext += '\n'

    if checkSpaceRatio(abstracttext):
        with open(os.path.join(text_directory, filename.replace('.grobid.tei.xml', '.txt')), 'w', encoding='utf-8') as f:
            f.write(abstracttext)
        return True
    else:
        with open(empty_abstract_file, 'w', encoding='utf-8') as extractfailfile:
            extractfailfile.write(filename.replace('.grobid.tei.xml', '.pdf') + '\n')
        return False

def ocrExtract(faillist):
    print("Attempting OCR extraction on failed papers...")
    paper_dir = pdffilepath
    # Create OCR directories
    createDir(imagedir)
    createDir(ocrtextdir)
    ocrsuccesses = 0
    ocrfails = 0
    with open(faillist, 'r') as f:
        for line in f:
            filename = line.strip()
            pdf_path = os.path.join(paper_dir, filename)
            try:
                doc = fitz.open(pdf_path)
                # Select the first page
                page = doc.load_page(0)  # page numbering starts from 0
                # Render the page to an image
                pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72)) # scales dpi by 300/72, i.e. to 300 dpi (Can modify based on quality requirements)
                image_path = imagedir + "{}.png".format(filename.split('.')[0])
                pix.save(image_path)
                # Use pytesseract to extract text from the image
                text = pytesseract.image_to_string(Image.open(image_path))
                # Write the extracted text
                with open(os.path.join(ocrtextdir, filename.replace('.pdf', '.txt')), 'w', encoding='utf-8') as f:
                    f.write(text)
                print("Extracted text from {}".format(filename))
                ocrsuccesses += 1
                # Close the document when done
                doc.close()
            except Exception as e:
                print("Error extracting text from {}".format(filename))
                print(e)
                ocrfails += 1
                problem_papers.append(filename)
                continue
            
    print("OCR Extraction successes: " + ocrsuccesses)
    print("OCR Extraction failures: " + ocrfails)
    print("Total: " + (ocrsuccesses + ocrfails))

    for filename in os.listdir(ocrtextdir):
        ocrAbsExtract(os.path.join(ocrtextdir, filename))


def ocrAbsExtract(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read().replace('\n', ' ')
        lower_content = content.lower()
        abstract_start = lower_content.find('abstract')
        # If "abstract" not found
        if abstract_start == -1:
            for term in ['introduction', 'synopsis', 'summary', 'overview', 'topic']:
                intro_start = lower_content.find(term)
                if intro_start != -1:
                    l = len(term)
                    break
            # If secondary search terms not found
            if intro_start == -1:
                problem_papers.append(filename.split('./ocrtexts\\')[1].replace('.txt', '.pdf'))
                return
            # If secondary search terms found, get 2000 characters after (ternary search terms may be inconsistent)
            else:
                intro_start += l
                content = content[intro_start:2000]
                with open(os.path.join('./ocrabstracts', filename.split('./ocrtexts\\')[1]), 'w', encoding='utf-8') as f:
                    f.write(content)
                maybe_problem_papers.append(filename.split('./ocrtexts\\')[1].replace('.txt', '.pdf'))
        else:
        # If "abstract" found
            abstract_start += 8
            content = content[abstract_start:]
            lower_content = lower_content[abstract_start:]
            for term in ['index terms', '1 introduction', 'introduction', '1. ', 'i.', 'keywords']:
                term_start = lower_content.find(term)
                if term_start != -1:
                    with open(os.path.join('./ocrabstracts', filename.split('./ocrtexts\\')[1]), 'w', encoding='utf-8') as f:
                        f.write(content[:term_start])
                    return
        # If end symbol not found, get 2000 characters after (ternary search terms may be inconsistent)
            maybe_problem_papers.append(filename.split('./ocrtexts\\')[1].replace('.txt', '.pdf'))
            print(filename + ": " + content[:1500])

if __name__ == "__main__":
    grobidExtract()