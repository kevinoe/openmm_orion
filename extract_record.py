from Standards import Fields
from openeye import oechem
from datarecord import OEField, Types
from cuberecord.cube_testing import OEMolRecordStream

ifs = OEMolRecordStream("SFEC.oedb")

for record in ifs:
    print(record.get_value(Fields.title))
    for field in record.get_fields():
        print(field.get_name())
    print(record.get_value(OEField("DG", Types.Float)))    
    # stages = record.get_value(Fields.md_stages)
    # stage = stages[-1]
    # print(stage.get_value(Fields.stage_name))
    # print(stage.get_value(Fields.log_data))
    # mdsystem = stage.get_value(OEField("MDSystem", Types.Record))
    # complex = mdsystem.get_value(OEField('Topology_OEMol', Types.Chem.Mol))
    # ofs = oechem.oemolostream("complex.oeb")
    # oechem.OEWriteConstMolecule(ofs, complex)

    # for field in mdsystem.get_fields():
    #     print(field.get_name())





# for record in ifs:
#     # stages = record.get_value(Fields.md_stages)
#     # stage = stages[0]
#     # print(stage.get_value(OEField("Log_data", Types.String)))
#
#     #print(stage.get_value(Fields.log_data))
#     # if record.has_value(OEField("Title_PLMD", Types.String)):
#     #     print(record.get_value(OEField("Title_PLMD", Types.String)))
#     for field in record.get_fields():
#         print(field.get_name())
#         type_field = field.get_type()
#         print(type_field)
#     # #print(record.get_value(OEField("DG", Types.Float)))
#     # protein = record.get_value(OEField("Protein", Types.Chem.Mol))
#     # ofs = oechem.oemolostream("protein"+str(count)+".oeb")
#     # oechem.OEWriteConstMolecule(ofs, protein)
#     count += 1