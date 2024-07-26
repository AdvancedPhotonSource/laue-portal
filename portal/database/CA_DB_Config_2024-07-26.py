from pathlib import Path

path = Path('config-calibrate3x1800-1.yml'); db = str(path.with_suffix('.db'))

sqlite_type_dict = {
                    'NoneType':'NULL',
                    'int':'INTEGER',
                    'float':'REAL',
                    'str':'TEXT',
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

table_columns = []
table_values = []
for k,(v,vt) in entries.items():
    print(k,(v,vt))
    table_columns.append(f'{k} {vt}')
    table_values.append(f'{v}')
    
#%%
import sqlite3

def create_tables():
    sql_statements = [
        
        f"""CREATE TABLE config
                {str(tuple(table_columns))}
        ;""",
        
        f"""INSERT INTO config
                VALUES {str(tuple(table_values))}
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
    create_tables()

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
