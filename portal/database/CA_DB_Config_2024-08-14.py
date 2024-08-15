from pathlib import Path

path = Path('config-calibrate3x1800-1.yml') #; db = str(path.with_suffix('.db'))
db = 'CA_params.db'

sqlite_type_dict = {
                    'NoneType':'NULL',
                    'str':'TEXT',
                    'float':'REAL',
                    'int':'INTEGER',
                    #:'BLOB',
                    'bool':'INTEGER',
                    }

#%%
def clean(line):
    c = '#'
    if c in line: line = line[:line.index('#')-1]
    else: line = line.rstrip('\n').rstrip()
    return line

classify_char = ':'
split_char = '-'

entries = {}; header_chain = []

with open(path, 'r') as f:
    lines = list(map(clean, f.readlines()))

for line in lines:
    if line:
        
        n_spaces = next((i for i, c in enumerate(line) if c != ' '))
        n_tabs = int(n_spaces/4)
        
        header_chain = header_chain[:n_tabs]
        
        local_header, value = line.split(classify_char) # *[p.lstrip() for p in line.split(':')]
        local_header = local_header.lstrip() #*
        header_chain.append(local_header)
        
        #print(local_header, value)
        if value:
            value = value.lstrip() #*
            full_header = split_char.join(header_chain)
            eval_value = eval(value)
            if isinstance(eval_value, (list, tuple)): # info on whether tuple or list not preserved
                for i,v in enumerate(eval_value):
                    entries[f'{full_header}_{i}'] = v,sqlite_type_dict[v.__class__.__name__]
            else:
                entries[full_header] = eval_value,sqlite_type_dict[eval_value.__class__.__name__]

config_table_columns = []
config_table_values = []
for k,(v,vt) in entries.items():
    print(k,(v,vt))
    config_table_columns.append(f'{k} {vt}')
    config_table_values.append(f'{v}')
    
#%%
import sqlite3

def create_config_table():
    sql_statements = [
        
        f"""CREATE TABLE config
                {str(tuple(config_table_columns))}
        ;""",
        
        f"""INSERT INTO config
                VALUES {str(tuple(config_table_values))}
        ;""",
        
        ]

    # create a database connection
    try:
        with sqlite3.connect(db) as conn:
            cursor = conn.cursor()
            for statement in sql_statements:
                cursor.execute(statement)
            
            conn.commit()
    except sqlite3.Error as e:
        print(e)


if __name__ == '__main__':
    create_config_table()

#%%    
# Import module 
import sqlite3 

# Connecting to sqlite 
conn = sqlite3.connect(db) 

# Creating a cursor object using the cursor() method 
cursor = conn.cursor() 


# Display columns 
print('\Config table:')
columns = cursor.execute('''SELECT * FROM config''').description
fields = [c[0].split() for c in columns]
for field in fields:
    #field_name, field_type = field
    print(field)

# Display data
print('\nData in Config table:')
vals = list(tuple(cursor.execute('''SELECT * FROM config'''))[0])
for val in vals:
    print(val)
    
# Commit your changes in the database     
conn.commit()

# Closing the connection 
conn.close()

#%%
path2 = path.with_stem(path.stem+'_db')

config_file_lines = []
flags = []
list_field_switch = False; list_field_name = ''; list_field_vals = []

for i,(field, val) in enumerate(zip(fields, vals)):
    print(i,(field, val))
    field_name, field_type = field
    if field_type == sqlite_type_dict['str']: val = f"'{val}'"
    labels = field_name.split(split_char)

    depth_count = field_name.count(split_char)
    
    if any([list_field_switch,'_' in field_name]):
        current_list_field_name = field_name.split('_')[0]
        if list_field_name:
            if any([current_list_field_name != list_field_name, i == len(fields)-1]):
                if i == len(fields)-1:
                    list_field_vals.append(val)
                list_field_labels = list_field_name.split(split_char)
                list_field_val = str(list_field_vals).translate({39: None})
                list_field_depth_count = list_field_name.count(split_char)
                file_line = f'{list_field_depth_count*(4*" ")}{list_field_labels[-1]}{classify_char} {list_field_val}'
                config_file_lines.append(file_line)
                list_field_switch = False; list_field_name = ''; list_field_vals = []
        
        if '_' in field_name:
            list_field_switch = True
            list_field_name = current_list_field_name
            list_field_vals.append(val)
    
    if depth_count > 0:
        for li,label in enumerate(labels[:-1]):
            flag = split_char.join(labels[:int(li+1)])
            if flag not in flags:
                flags.append(flag)
                file_line = f'{li*(4*" ")}{label}{classify_char}'
                config_file_lines.append('')
                config_file_lines.append(file_line)
    
    if '_' not in field_name:        
        file_line = f'{depth_count*(4*" ")}{labels[-1]}{classify_char} {val}'
        config_file_lines.append(file_line)

with open(path2,'w') as f:
    f.writelines([l+'\n' for l in config_file_lines])

#%%
import sqlite3
import csv

db = 'CA_params.db'

params_tables_fields_files = [Path(f).with_suffix('.csv') for f in
                               [
                                'metadata',
                                'calib',
                                'recon',
                                ]]

params_tables_fields = []
for file in params_tables_fields_files:
    with open(file,'r') as f:
        csvFile = csv.reader(f, delimiter='\t')
        for i,line in enumerate(csvFile):
            if i == 0:
                params_tables_fields.append(line)
            else:
                pass

metadata_fields = [
  'Dataset ID',
  'Dataset path',
  'Dataset filename',
  'Type',
  'Group',
  'start time',
  'end time',
  'start image #',
  'end image #',
  'total points',
  'maskX/wireBaseX',
  'maskY/wireBaseY',
  'maskZ/wireBaseZ',
  'SR1 motor',
  'motion',
  'SR1 init',
  'SR1 final',
  'SR1 step',
  'SR2 motor',
  'SR2 init',
  'SR2 final',
  'SR2 step',
  'SR3 motor',
  'SR3 init',
  'SR3 final',
  'SR3 step',
  'shift parameter',
  'exp time [s]',
  'mda',
  'sampleXini',
  'sampleYini',
  'sampleZini',
  'Comment',
  ]

calib_fields = [
  'Calib ID',
  'Date',
  'Commit ID',
  'Runtime',
  'Computer name',
  'Config (Calibration Input)',
  'Dataset ID',
  'Dataset path',
  'Dataset filename',
  'Notes',
  'cenx (Z)',
  'dist (Y)',
  'anglez',
  'angley',
  'anglex',
  'cenz (X)',
  'shift parameter',
  'Comment',
  ]

recon_fields = [
  'Recon ID',
  'Date',
  'Commit ID for recon',
  'Calib ID',
  'Runtime',
  'Computer name',
  'Config',
  'Dataset ID',
  'Dataset path',
  'Dataset filename',
  'Notes',
  'Depth_start',
  'Depth_End',
  'Depth_Step',
  'cenx (Z)',
  'dist (Y)',
  'anglez',
  'angley',
  'anglex',
  'cenz (X)',
  'shift parameter',
  'folder recon results',
  'pixel-mask',
  'indexing_hpcs_cluster',
  ]

#***#

metadata_str_fields = [
  'Type',
  'Group',
  'start time',
  'end time',
  'Dataset path',
  'Dataset filename',
  'Comment',
  ]

metadata_int_fields = [
  'Dataset ID',
  'start image #',
  'end image #',
  'total points',
  'mda',
  ]

metadata_float_fields = [
  'maskX/wireBaseX',
  'maskY/wireBaseY',
  'maskZ/wireBaseZ',
  'SR1 motor',
  'motion',
  'SR1 init',
  'SR1 final',
  'SR1 step',
  'SR2 motor',
  'SR2 init',
  'SR2 final',
  'SR2 step',
  'SR3 motor',
  'SR3 init',
  'SR3 final',
  'SR3 step',
  'shift parameter',
  'exp time [s]',
  'sampleXini',
  'sampleYini',
  'sampleZini',
  ]

calib_str_fields = [
  'Date',
  'Commit ID',
  'Runtime',
  'Config (Calibration Input)',
  'Dataset path',
  'Dataset filename',
  'Notes',
  'Computer name',
  ]

calib_int_fields = [
  'Calib ID',
  'Dataset ID',
  ]

calib_float_fields = [
  'cenx (Z)',
  'dist (Y)',
  'anglez',
  'angley',
  'anglex',
  'cenz (X)',
  'shift parameter',
  ]

recon_str_fields = [
  'Date',
  'Commit ID for recon',
  'Runtime',
  'Computer name',
  'Config',
  'Dataset path',
  'Dataset filename',
  'Notes',
  'folder recon results',
  'pixel-mask',
  'indexing_hpcs_cluster',
  ]

recon_int_fields = [
  'Recon ID',
  'Dataset ID',
  'Calib ID',
  ]

recon_float_fields = [
  'Depth_start',
  'Depth_End',
  'Depth_Step',
  'cenx (Z)',
  'dist (Y)',
  'anglez',
  'angley',
  'anglex',
  'cenz (X)',
  'shift parameter',
  ]

metadata_type_dict = {
                      'str':metadata_str_fields,
                      'float':metadata_float_fields,
                      'int':metadata_int_fields,
                     }

calib_type_dict = {
                   'str':calib_str_fields,
                   'float':calib_float_fields,
                   'int':calib_int_fields,
                   }

recon_type_dict = {
                   'str':recon_str_fields,
                   'float':recon_float_fields,
                   'int':recon_int_fields,
                   }

#%%
def create_params_tables():
    
    def add_field_type(e,field_type='str'):
        return f"'{e}' {sqlite_type_dict[field_type]}"
    
    def format_key_header(e):
        return f"{e} NOT NULL"
    
    mask_focus_fields = [
                        'cenx (Z)',
                        'dist (Y)',
                        'anglez',
                        'angley',
                        'anglex',
                        'cenz (X)',
                        'shift parameter',
                        ]
    
    def format_specified_header(e):
        return f"specified {e}"
    
    specified_mask_focus_fields = list(map(format_specified_header, mask_focus_fields))
    
    pos = recon_fields.index(mask_focus_fields[-1])+1
    recon_fields[pos:pos] = specified_mask_focus_fields
    
    pos_ = recon_float_fields.index(mask_focus_fields[-1])+1
    recon_float_fields[pos_:pos_] = specified_mask_focus_fields
    recon_type_dict['float'] = recon_float_fields
    
    metadata_key_fields = ['Dataset ID'] + ['Dataset path','Dataset filename']
    calib_key_fields = ['Calib ID'] + mask_focus_fields
    recon_key_fields = ['Recon ID']
    
    str_metadata_key_fields = str(tuple(metadata_key_fields))
    str_calib_key_fields = str(tuple(calib_key_fields))
    str_recon_key_fields = str(tuple(recon_key_fields))    
    
    def format_fields(fields,field_dict,key_fields=[]):
        headers = []
        for field in fields:
            for field_type in field_dict.keys():
                if field in field_dict[field_type]:
                    header = add_field_type(field,field_type=field_type)
                    if field in key_fields:
                        header = format_key_header(header)
                    headers.append(header)
        return headers
    
    metadata_headers = format_fields(metadata_fields, metadata_type_dict)
    calib_headers = format_fields(calib_fields, calib_type_dict, calib_key_fields)
    recon_headers = format_fields(recon_fields, recon_type_dict, calib_key_fields)
    
    metadata_table_columns = metadata_headers + \
                             [f'PRIMARY KEY {str_metadata_key_fields}'] + \
                             []
    
    calib_table_columns = calib_headers + \
                          [f'PRIMARY KEY {str_calib_key_fields}'] + \
                          [f'FOREIGN KEY {str_metadata_key_fields} \
                           REFERENCES metadata{str_metadata_key_fields}'] + \
                          []
                          
    recon_table_columns = recon_headers + \
                          [f'PRIMARY KEY {str_recon_key_fields}'] + \
                          [f'FOREIGN KEY {str_metadata_key_fields} \
                           REFERENCES metadata{str_metadata_key_fields}'] + \
                          [f'FOREIGN KEY {str_calib_key_fields} \
                           REFERENCES calib{str_calib_key_fields}'] + \
                          []
    
    sql_statements = [
        
        f"""CREATE TABLE metadata
                {str(tuple(metadata_table_columns))}
        ;""",
        
        f"""CREATE TABLE calib
                {str(tuple(calib_table_columns))}
        ;""",
        
        f"""CREATE TABLE recon
                {str(tuple(recon_table_columns))}
        ;""",
        
        ]

    # create a database connection
    try:
        with sqlite3.connect(db) as conn:
            cursor = conn.cursor()
            for statement in sql_statements:
                cursor.execute(statement)
            
            conn.commit()
    except sqlite3.Error as e:
        print(e)


if __name__ == '__main__':
    create_params_tables()
    
#%%
# Import module 
import sqlite3 

# Connecting to sqlite 
conn = sqlite3.connect(db) 

# Creating a cursor object using the cursor() method 
cursor = conn.cursor() 


##
# # Getting all tables from sqlite_master
# sql_query = """SELECT name FROM sqlite_master 
# WHERE type='table';"""

# # Creating cursor object using connection object
# cursor = sqliteConnection.cursor()

# # executing our sql query
# cursor.execute(sql_query)
# print("List of tables\n")

# # printing all tables list
# print(cursor.fetchall())
##

# Display columns 
print('\Config table:')
columns = cursor.execute('''SELECT * FROM config''').description
fields = [c[0].split()[0] if 'KEY' not in c[0] else c[0] for c in columns]
for field in fields:
    #field_name, field_type = field
    print(field)

# Display columns 
print('\Calib table:')
columns = cursor.execute('''SELECT * FROM recon''').description
fields = [c[0].split()[0] if 'KEY' not in c[0] else c[0] for c in columns]
for field in fields:
    #field_name, field_type = field
    print(field)

# Display columns 
print('\Recon table:')
columns = cursor.execute('''SELECT * FROM calib''').description
fields = [c[0].split()[0] if 'KEY' not in c[0] else c[0] for c in columns]
for field in fields:
    #field_name, field_type = field
    print(field)

# # Display data
# print('\nData in Config table:')
# vals = list(tuple(cursor.execute('''SELECT * FROM recon'''))[0])
# for val in vals:
#     print(val)
    
# Commit your changes in the database     
conn.commit()

# Closing the connection 
conn.close()