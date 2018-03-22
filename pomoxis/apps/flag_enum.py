from enum import Enum


#States of the shared flags (set as enums):
# - Clearing
# - Empty
# - Instrand_ignore (Something in the pore but we don't want to run jobs)
# - Instrand_check (Something in the pore and we do want to run the job)

class flag(Enum):
	Empty = 0
	Clearing = 1
	Instrand_ignore = 2
	Instrand_check = 3