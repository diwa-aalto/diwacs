'''
Created on 1.6.2012

@author: neriksso
'''
import controller
import utils
import sys

def main():
    if len(sys.argv) == 3:
        project_id = sys.argv[1]
        filepath = sys.argv[2]
        controller.add_file_to_project(filepath, project_id)
if __name__ == '__main__':
    main()