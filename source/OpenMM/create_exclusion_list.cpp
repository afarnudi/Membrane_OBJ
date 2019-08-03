#include "Membrane.h"
#include "General_functions.hpp"
#include "OpenMM_structs.h"
#include "OpenMM_funcs.hpp"


const int EndOfList=-1;

std::vector< std::pair< int, int > > exclusion_list_generator(Bonds*      bonds,
                                                              std::string label_1,
                                                              std::string label_2){
    
    std::vector< std::pair< int, int > > exclude_bonds;
    
    for (int i_b=0; bonds[i_b].type != EndOfList; ++i_b) {
        
        if (bonds[i_b].class_label == label_1) {
            std::pair< int, int > temp;
            temp.first=bonds[i_b].atoms[0];
            temp.second=bonds[i_b].atoms[1];
            exclude_bonds.push_back(temp);
        }
        
        if (bonds[i_b].class_label == label_2) {
            std::pair< int, int > temp;
            temp.first=bonds[i_b].atoms[0];
            temp.second=bonds[i_b].atoms[1];
            exclude_bonds.push_back(temp);
        }
        
        
    }
    return exclude_bonds;
}