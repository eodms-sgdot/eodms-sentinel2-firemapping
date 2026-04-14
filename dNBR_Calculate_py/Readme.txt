The codes present in this folder can perform the following tasks:
1) The code uses NFDB large fire polygons as present in the data folder. The data gets downloaded into folders named after the fire_id. 
2) CSV files have records of what data was downloaded for which fire_id for later reference.
3) Download a less than 30% cloud image for Post Fire: reported date +30 to reported date +45 for eample. Can be changed according to your preference.
  --- sometimes we dont get any good image even upto 45 days, for example fire_id '2020-V51227' changing the end date to 60, brough one on 59th day.
4) Download a less than 30% cloud image for Pre Fire: Reported date - 15 to reported date -10 for example. Can be changed according to your preference.
  --- you can change the cloud percentage to lower levels if it is interfering the fire polygon.
5) Calculate NBR for Pre Fire and Post Fire scenarios, and then mask with classes 4,5 and 7 (to avoid water and clouds).
  --- you can change the mask classes. 5 is for vegetation, but 4 is relevant, since burnt area will be barren and 7 is useful since its unclassified.
6) Calculate difference in NBR (dNBR) between Pre-Fire and Post Fire scenarios.
  --- a simple substraction is performed and choosing a pseudo color symbology with a starting value greater than 0.25 is recommended by research articles.
7) Visualize the dNBR image rendered with correct symbology (greater than 0.25) along with the NFDB fire polygons to see the value of the process. 
8) If the polygon is not filled, the result:
      a) may be more precise
      b) can be improved if a later image was chosen for post fire image.
      c) can be improved if a less cloudy image was chosen, if cloud covered the polygon at 30% choice.
      d) can be improved if masking can be changed from 4,5,7 classes, check the unmasked NBR.
