"""Synthetic tests of strict saved parent-class mitigation evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.trace_silverhand_saved_armour_ancestry import PREFIX, trace, LEAF


class SilverhandArmourTraceTests(unittest.TestCase):
    def make_graph(self, root, *, base_armour="EArmourType::Tier2Tank",
                   child_override=None, cycle=False):
        structs = [
            ("BPMediumTankW", "MediumTankBaseW",
             {"CodeName": "MediumTankW", **(
                 {"ArmourType": child_override} if child_override else {})}),
            ("MediumTankBaseW", "BPMediumTankBase", {}),
            ("BPMediumTankBase", "BPMediumTankW" if cycle else None,
             {"ArmourType": base_armour}),
        ]
        folder = root / "Vehicles/MediumTank"
        folder.mkdir(parents=True)
        for name, parent, props in structs:
            path = folder / (name + ".json")
            sup = {"ObjectPath": PREFIX + "Vehicles/MediumTank/" + parent + ".1"} if parent else {
                "ObjectPath": "/Script/War"}
            path.write_text(json.dumps([
                {"Type":"BlueprintGeneratedClass","Name":name+"_C","SuperStruct":sup},
                {"Type":"SavedDefault", "Name":"Default__"+name+"_C","Properties":props}
            ]))

    def original_tags(self):
        return ("TYPE\t" + PREFIX + "Vehicles/MediumTank/BPMediumTankBase.uasset" +
                "\tDefault__BPMediumTankBase_C\tArmourType\tEnumProperty")

    def test_exact_unique_saved_ancestor(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.make_graph(root)
            result=trace(root,self.original_tags())
            self.assertEqual(result["source_status"],
                "exact_saved_ancestor_declaration_matches_human")
            self.assertEqual(len(result["chain"]),3)
            self.assertEqual(result["native_effective_inheritance"], "unverified")

    def test_missing_type_proof_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.make_graph(root)
            result=trace(root,"TYPE\tUnrelated\tDefault__X\tOther\tNameProperty")
            self.assertEqual(result["source_status"],"saved_category_original_tag_unverified")

    def test_wrong_armour_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.make_graph(root,base_armour="EArmourType::Tier1Tank")
            result=trace(root,self.original_tags())
            self.assertEqual(result["source_status"],"saved_armour_category_disagrees_with_human")

    def test_child_override_is_ambiguous_for_strict_audit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.make_graph(root,child_override="EArmourType::Tier3Tank")
            result=trace(root,self.original_tags())
            self.assertEqual(result["source_status"],"missing_or_conflicting_saved_armour_declarations")

    def test_cycle_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.make_graph(root,cycle=True)
            with self.assertRaisesRegex(ValueError,"Cyclic"):
                trace(root,self.original_tags())


if __name__ == "__main__":
    unittest.main()
