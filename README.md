# goes-dcs
## What is it??
A processor for GOES-R HRIT files containing Data Collection System Data<br/>
Currently written in Python for simplicity

## Usage
To use simply run:<br/> 
`python dcs.py <HRIT Binary File>`<br/>

To acquire the files necessary you can utilize [pietern/goestools](https://github.com/pietern/goestools).<br/>
Make sure you already have goesrecv running and then run this command:<br/>
`goeslrit --subscribe tcp://localhost:5004 --dcs --out <output dir>`
