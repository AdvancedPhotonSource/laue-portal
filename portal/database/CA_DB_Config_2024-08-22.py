from pathlib import Path
import sqlite3
import csv

db = 'CA_params.db'

dev = True #True False
if dev: Path.unlink(db,missing_ok=True) #delete db

sql_class_dict = {
                    'NoneType':'NULL',
                    'str':'TEXT',
                    'float':'REAL',
                    'int':'INTEGER',
                    #:'BLOB',
                    'bool':'INTEGER',
                    }

def make_table_str(my_list):
    str_list = map(str,my_list)
    my_str = f"({', '.join(str_list)})"
    return my_str

def make_fields_str(my_list):
    str_list = map(str,my_list)
    if len(my_list) > 1:
        my_str = f"{tuple(str_list)}"
    else:
        my_str = f"('{''.join(str_list)}')"
    return my_str

#%%
params_tables_fields_files = [Path(f).with_suffix('.csv') for f in
                             [
                              'metadata',
                              'calib',
                              'recon',
                             ]]


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
  'anglez (angleX)',
  'angley (angleY)',
  'anglex (angleZ)',
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
  'Depth_Start',
  'Depth_End',
  'Depth_Step',
  'cenx (Z)',
  'dist (Y)',
  'anglez (angleX)',
  'angley (angleY)',
  'anglex (angleZ)',
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
  'anglez (angleX)',
  'angley (angleY)',
  'anglex (angleZ)',
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
  'Depth_Start',
  'Depth_End',
  'Depth_Step',
  'cenx (Z)',
  'dist (Y)',
  'anglez (angleX)',
  'angley (angleY)',
  'anglex (angleZ)',
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
mask_focus_fields = [
                    'cenx (Z)',
                    'dist (Y)',
                    'anglez (angleX)',
                    'angley (angleY)',
                    'anglex (angleZ)',
                    'cenz (X)',
                    'shift parameter',
                    ]

def create_params_tables():
    
    def add_field_class(e,field_type='str'):
        return f"'{e}' {sql_class_dict[field_type]}"
    
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
    
    str_metadata_key_fields = make_fields_str(metadata_key_fields)
    str_calib_key_fields = make_fields_str(calib_key_fields)
    str_recon_key_fields = make_fields_str(recon_key_fields) 
    
    def format_fields(fields,type_dict,key_fields=[]):
        headers = []
        for field in fields:
            for field_type in type_dict.keys():
                if field in type_dict[field_type]:
                    header = add_field_class(field,field_type=field_type)
                    headers.append(header)
        return headers
    
    metadata_headers = format_fields(metadata_fields, metadata_type_dict)
    calib_headers = format_fields(calib_fields, calib_type_dict)
    recon_headers = format_fields(recon_fields, recon_type_dict)
    
    metadata_table_columns = metadata_headers + \
                             [f'PRIMARY KEY{str_metadata_key_fields}'] + \
                             []
    
    calib_table_columns = calib_headers + \
                          [f'PRIMARY KEY{str_calib_key_fields}'] + \
                          [f'FOREIGN KEY{str_metadata_key_fields} \
                           REFERENCES metadata{str_metadata_key_fields}'] + \
                          []
                          
    recon_table_columns = recon_headers + \
                          [f'PRIMARY KEY{str_recon_key_fields}'] + \
                          [f'FOREIGN KEY{str_metadata_key_fields} \
                           REFERENCES metadata{str_metadata_key_fields}'] + \
                          [f'FOREIGN KEY{str_calib_key_fields} \
                           REFERENCES calib{str_calib_key_fields}'] + \
                          []
    
    sql_statements = [
        
        f"""CREATE TABLE metadata
                {make_table_str(metadata_table_columns)}
        ;""",
        
        f"""CREATE TABLE calib
                {make_table_str(calib_table_columns)}
        ;""",
        
        f"""CREATE TABLE recon
                {make_table_str(recon_table_columns)}
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
def table_output(table_name,cursor):
    
    # Display columns 
    print(f'\{table_name} table:')
    columns = cursor.execute(f'''SELECT * FROM {table_name}''').description
    fields = [c[0].split()[0] for c in columns]
    for field in fields: print(field)
    
    # Display data
    print(f'\nData in {table_name} table:')
    vals = tuple(cursor.execute(f'''SELECT * FROM {table_name}'''))
    if vals: vals = list(vals[0])
    for val in vals: print(val)
    
    return fields,vals

# Connecting to sqlite 
conn = sqlite3.connect(db) 

# Creating a cursor object using the cursor() method 
cursor = conn.cursor()

table_output('metadata',cursor)
table_output('calib',cursor)
table_output('recon',cursor)

# # Commit your changes in the database     
# conn.commit()

# Closing the connection 
conn.close()

#%%
path = Path('config-calibrate3x1800-1.yml') #; db = str(path.with_suffix('.db'))

def clean(line):
    c = '#'
    if c in line: line = line[:line.index('#')-1]
    else: line = line.rstrip('\n').rstrip()
    return line

classify_char = ':'
split_char = '-'

def read_config(path):
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
                        entries[f'{full_header}_{i}'] = v,sql_class_dict[v.__class__.__name__]
                else:
                    entries[full_header] = eval_value,sql_class_dict[eval_value.__class__.__name__]
    
    config_fields = []
    config_classes = []
    config_values = []
    for f,(v,c) in entries.items():
        print(f,(v,c))
        config_fields.append(f'{f}')
        config_classes.append(f'{c}')
        config_values.append(f'{v}')
        
    return config_fields,config_classes,config_values

config_info = read_config(path)
config_fields, config_classes, config_values = config_info

#%%
expanded_config_fields = ['config'] + config_fields
expanded_config_classes = [sql_class_dict['str']] + config_classes
expanded_config_values = [str(path)] + config_values

config_to_db_dict = {
                     'config': 'Config',
                     'file-output': 'folder recon results',
                     'geo-mask-shift': 'shift parameter',
                     'geo-mask-focus-cenx': 'cenx (Z)',
                     'geo-mask-focus-dist': 'dist (Y)',
                     'geo-mask-focus-anglez': 'anglez (angleX)',
                     'geo-mask-focus-angley': 'angley (angleY)',
                     'geo-mask-focus-anglex': 'anglex (angleZ)',
                     'geo-mask-focus-cenz': 'cenz (X)',
                     'geo-source-grid_0': 'Depth_Start',
                     'geo-source-grid_1': 'Depth_End',
                     'geo-source-grid_2': 'Depth_Step',
                    }

config_to_db_group_dict = {
                           'metadata': ([],[],[]),
                           'calib': ([],[],[]),
                           'recon': ([],[],[]),
                          }

for k,v in config_to_db_dict.items():
    flag = 'recon'
    if k in expanded_config_fields:
        i = expanded_config_fields.index(k)
        if v in mask_focus_fields:
            flag = 'calib'
        config_to_db_group_dict[flag][0].append(config_to_db_dict[expanded_config_fields[i]])
        config_to_db_group_dict[flag][1].append(expanded_config_classes[i])
        config_to_db_group_dict[flag][2].append(expanded_config_values[i])
        
#%%
def construct_table(table,fields,classes,values=None,db=db):
    
    def make_column(f,c):
        return f"'{f}' {c}"
    
    columns = list(map(make_column, fields, classes))
    
    fields_str = make_fields_str(fields)
    columns_str = make_table_str(columns)

    # create a database connection
    try:
        with sqlite3.connect(db) as conn:
            cursor = conn.cursor()
            
            if columns:
                sql_table_statement = f"""CREATE TABLE IF NOT EXISTS {table}
                                          {columns_str}
                                      ;"""
                cursor.execute(sql_table_statement); conn.commit()
            
            if values:
                values_str = make_fields_str(values)
                sql_insert_statement = f"""INSERT INTO {table}{fields_str}
                                           VALUES{values_str}
                                       ;"""
                cursor.execute(sql_insert_statement); conn.commit()
            
    except sqlite3.Error as e:
        print(f"{table} error:")
        print(e)


if __name__ == '__main__':
    construct_table('config',*config_info)
    for table_name in config_to_db_group_dict.keys():
        construct_table(table_name,*config_to_db_group_dict[table_name])
    
#%%    
# Import module 
import sqlite3 

# Connecting to sqlite 
conn = sqlite3.connect(db) 

# Creating a cursor object using the cursor() method 
cursor = conn.cursor()

fields, vals = table_output('config',cursor)

# # Commit your changes in the database     
# conn.commit()

# Closing the connection 
conn.close()

#%%
path2 = path.with_stem(path.stem+'_db')

config_file_lines = []
flags = []
list_field_switch = False; list_field = ''; list_vals = []

for i,(field, val) in enumerate(zip(fields, vals)):
    print(i,(field, val))
    
    if isinstance(val, str): val = f"'{val}'"
    labels = field.split(split_char)

    depth_count = field.count(split_char)
    
    if any([list_field_switch,'_' in field]):
        current_list_field = field.split('_')[0]
        if list_field:
            if any([current_list_field != list_field, i == len(fields)-1]):
                if i == len(fields)-1:
                    list_vals.append(val)
                list_field_labels = list_field.split(split_char)
                list_field_val = str(list_vals).translate({39: None})
                list_field_depth_count = list_field.count(split_char)
                file_line = f'{list_field_depth_count*(4*" ")}{list_field_labels[-1]}{classify_char} {list_field_val}'
                config_file_lines.append(file_line)
                list_field_switch = False; list_field = ''; list_vals = []
        
        if '_' in field:
            list_field_switch = True
            list_field = current_list_field
            list_vals.append(val)
    
    if depth_count > 0:
        for li,label in enumerate(labels[:-1]):
            flag = split_char.join(labels[:int(li+1)])
            if flag not in flags:
                flags.append(flag)
                file_line = f'{li*(4*" ")}{label}{classify_char}'
                config_file_lines.append('')
                config_file_lines.append(file_line)
    
    if '_' not in field:        
        file_line = f'{depth_count*(4*" ")}{labels[-1]}{classify_char} {val}'
        config_file_lines.append(file_line)

with open(path2,'w') as f:
    f.writelines([l+'\n' for l in config_file_lines])
