import os
import streamlit as st
from dotenv import load_dotenv
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes, ComputerVisionOcrErrorException
from msrest.authentication import CognitiveServicesCredentials
import warnings
from io import BytesIO
import time
import pandas as pd

# Ignore specific warnings from pydub
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work", category=RuntimeWarning, module='pydub.utils')

def main():
    # Load environment variables
    load_dotenv()
    
    # Streamlit app setup
    st.title("Invoice Data Extractor")
    st.markdown("##### Extract Data from Electricity Invoices and Save to CSV")

    # Azure credentials
    azure_key = os.getenv('AZURE_KEY')
    azure_endpoint = os.getenv('AZURE_ENDPOINT')

    if not azure_key or not azure_endpoint:
        st.error("Azure credentials are not set in the environment variables.")
        return

    credentials = CognitiveServicesCredentials(azure_key)
    client = ComputerVisionClient(azure_endpoint, credentials)

    def extract_text_from_stream(image_stream, client):
        try:
            response = client.read_in_stream(image_stream, raw=True)
            operation_location = response.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            while True:
                result = client.get_read_result(operation_id)
                if result.status not in ['notStarted', 'running']:
                    break
                time.sleep(1)

            extracted_text = ""
            if result.status == OperationStatusCodes.succeeded:
                for text_result in result.analyze_result.read_results:
                    for line in text_result.lines:
                        extracted_text += line.text + "\n"

            return extracted_text.strip()
        except ComputerVisionOcrErrorException as e:
            st.error(f"Computer Vision OCR error: {e.message}")
            return ""

    def extract_invoice_data(text):
        lines = text.split('\n')
        account_number = None
        water_consumption = None
        electric_usage = None

        for line in lines:
            if "Account Number" in line:
                account_number = line.split(":")[-1].strip()
            elif "Water Consumption" in line:
                water_consumption = line.split(":")[-1].strip()
            elif "Electric Usage" in line:
                electric_usage = line.split(":")[-1].strip()
        
        return account_number, water_consumption, electric_usage

    def save_to_csv(data, filename='invoice_data.csv'):
        df = pd.DataFrame(data, columns=['Account Number', 'Water Consumption', 'Electric Usage'])
        df.to_csv(filename, index=False)

    img_file_buffer = st.file_uploader("Upload images (jpg, png, jpeg):", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if st.button("Extract Data and Save to CSV"):
        if img_file_buffer:
            all_data = []

            for img_file in img_file_buffer:
                # Convert the file buffer to an image stream
                image_stream = BytesIO(img_file.getvalue())

                # Extract text from the image
                extracted_text = extract_text_from_stream(image_stream, client)
                
                # Extract invoice data
                account_number, water_consumption, electric_usage = extract_invoice_data(extracted_text)
                
                if account_number and water_consumption and electric_usage:
                    all_data.append((account_number, water_consumption, electric_usage))
                else:
                    st.warning(f"Failed to extract all required data from the image: {img_file.name}")

            if all_data:
                save_to_csv(all_data)
                st.success("Data extracted and saved to CSV successfully!")
                st.write("Extracted Data:")
                st.write(pd.DataFrame(all_data, columns=['Account Number', 'Water Consumption', 'Electric Usage']))
            else:
                st.error("No data extracted from the uploaded images.")
                
if __name__ == "__main__":
    main()
