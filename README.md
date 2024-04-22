# PeopleWeave Intelligent Paper Abstract Extraction

Extracts the abstract from a PDF file using GROBID models first and then resorting to OCR. May retrain GROBID in future.

## Setup

1. Install Tesseract OCR with the instructions found here: https://tesseract-ocr.github.io/tessdoc/Installation.html

2. Clone the grobid python client (in the working directory):

   ```
   git clone https://github.com/kermitt2/grobid_client_python
   ```

   OPTIONAL, install CLI:

   ```
   cd grobid_client_python
   python3 setup.py install
   cd ..
   ```

3. Modify grobid.yaml and run the Grobid Server Docker image.
   There are two options, you can use the full Grobid image with deep learning models (accuracy better, long installation and runtime, ideal for small # of pdfs, a good machine, and ideally a GPU) or the lightweight image without DL models (for efficiency, low resources, lots of pdfs). You must have Docker installed for both options, and make sure the engine is running.

   - Full image:
     For more accurate abstract extraction (header model) e.g using a BiLSTM fed into a ChainCRF (and can also use a SciBert transformer). grobid.yaml is configured for this by default.
     Ensure that the concurrency parameter in the grobid.yaml file is set according to your CPU/GPU capacity and matches here (default 10 should be okay).
     Installation takes a while, but you only need to do it once.
     Command:
     ```
     docker run --rm --gpus all --init --ulimit core=0 -p 8070:8070 -p 8071:8071 -v {Full path to local grobid.yaml}:/opt/grobid/grobid-home/config/grobid.yaml:ro grobid/grobid:0.8.0
     ```
   - Lightweight image:
     The lightweight image is much faster to install and run and doesn't use DL models (only linear chain CRFs).
     **Important**: In grobid.yaml, simply modify the engine parameter of the "header" model to be "wapiti" instead of "delft" (line 117 and 118).
     Ensure that the concurrency parameter in the grobid.yaml file is set according to your CPU capacity and matches here (default 10 should be okay).
     Command:
     ```
     docker run --rm --init --ulimit core=0 -p 8070:8070 -p 8071:8071 -v {Full path to local grobid.yaml}:/opt/grobid/grobid-home/config/grobid.yaml:ro lfoppiano/grobid:0.8.0
     ```
     In theory, runtime and params shouldn't be an issue since we generally have a small number of new papers to process.

4. Open a new terminal and clone this repository in the working directory (i.e. the **parent directory of grobid_client_python**) and install dependencies:
   ```
   git clone https://github.com/nehangit/extract_tool.git
   cd extract_tool
   pip install -r requirements.txt
   ```

## Usage

Ensure that the GROBID container is running on a separate terminal, then use:

```
python grobidExtract.py
```

By default, this looks for a directory "Conference Papers", uses 10 threads, and does abstract extraction.

To change these options, see the help menu:

```
python grobidExtract.py -h
```

## Notes

- Runtime depends on models used, model parameters, number of PDFs, and number of threads ("concurrency") all are specified in the grobid.yaml file.
- Configuration docs for grobid.yaml: https://grobid.readthedocs.io/en/latest/Configuration/
- I've ran into issues with GROBID if full paths become too long, move the project to a previous/shorter directory.
- Using DL engine recommended for certain models other than header, depends on your use cases see https://grobid.readthedocs.io/en/latest/Deep-Learning-models/
- If using Linux/macOS and want to train the models, you can build GROBID from source, see grobid docs for details.
- WORK IN PROGRESS
