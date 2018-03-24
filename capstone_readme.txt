Running pomoxis:
Do a “make install” in the pomoxis home directory
Run . ./venv/bin/activate to set a virtual environment to run pomoxis in

When in the virtual  environment, you might need to make sure the magenta/ dct modules are installed as they might not be carried over:

	Navigate back to the magenta wrapper and run the install if this happens.

Basic command to run pomoxis in the virtual environment:

	Navigate to the apps directory in pomoxis and run the following command to run the readUntil:
	python read_until_filter.py /home/sjhepbur/minioncapstone/sample_data/E_coli/ecoli_genome.fna positive /home/gordonp/bulk_fast5/MSI_20180314_FAH40082_MN24809_sequencing_run_mt237_3_brdu_mcginty_54076.fast5 1-512

Run . ./venv/bin/deactivate to exit the virtual environment when done
