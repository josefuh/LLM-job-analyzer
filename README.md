# LLM job analyzer
For MIUN course DT002G, VT2025 and exjobb DT133G VT2025.
Created by Josef Al irani and Oscar Ljungh.

## Setup

```commandline
    pip install -r requirements.txt
```

## Usage

### Fetching job ads
Under the 'Data collection' header in the top-left of the application, a form is available for assigning parameters for
before fetching ads. 

+ The 'Location' field is optional, and allows for specifying a city/county/other location that the job ads has to be located in. Leaving this field empty allows gathering job ads regardless of location.
+ The 'max listings' field specifies how many ads should be retrieved in total. 
+ Because the program fetches ads in multiple batches, the 'batch size' field controls how many ads are requested at a time.
+ To specify a specific date range for when the ads are posted, checking the 'use date range' checkbox enables two date-picker
fields to be changed. 
  + If the checkbox is unchecked, the program uses the default date range of 2022-01-01 to the current
  date.
+ To select what API are used to fetch job ads, there are two checkboxes listed under the 'data source' field. 
  + 'Platsbanken' is an API linked to currently active listings on the Swedish Public Employment Service (Platsbanken). 
  + 'Platsbanken historical data' retrieves expired job ads that have been listed previously on Platsbanken.


+ To Start fetching ads, clicking the button labeled 'fetch listings' starts the process which is can be canceled any time 
by clicking the 'cancel'-button. 
+ The 'clear all listings' button removes all previously fetched job ads that have been stored
locally.

### Analyzing the data
To generate graphs after having gathered job ads, it can be done by clicking the 'Analysis' tab to the right of the 'Data Collection'
header. 

+ Three types of graphs are available, and selecting what graphs are to be generated can be done by checking the associated 
checkboxes. 
+ To change what date range for when job ads have been posted is used when creating the graphs, it can be done 
by using the two date-picker fields.


+ The graphs can then be created by clicking the 'Run Analysis' button, the graphs are then displayed below when finished.
+ To export the graphs as PNG images, it can be done by clicking the 'export graphs' button that then prompts to select a file
location to export the graphs to. 
+ By pressing the 'export analysis data' can the data used to perform the analysis be exported
as a .csv file. 

### Browsing results
All the gathered job postings can be viewed under the 'browse listings' section. This scrollable list specifies when each
ad was posted, from which API it was retrieved from, what identified role is advertised, and whether it is related to prompt
engineering (PE) or not. The browser also allows for applying filters and search criteria to be able to view specific ads
from the results. The gathered ads can be exported with the 'export results'-button, which creates a .csv file containing
the data for each job post.