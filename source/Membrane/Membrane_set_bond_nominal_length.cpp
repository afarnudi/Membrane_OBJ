//
//  check.cpp
//  Mem
//
//  Created by Ali Farnudi on 24/09/2020.
//  Copyright © 2018 Ali Farnudi. All rights reserved.
//

#include "Membrane.h"


void Membrane::set_bond_nominal_length(void){
    Node_Bond_distances.clear();
    Node_Bond_distances.resize(Num_of_Node_Pairs);
    
    if (Node_Bond_distances_stat=="Au") {
        
        for (int i=0; i<Num_of_Node_Pairs; i++) {
            Node_Bond_distances[i] = sqrt( (Node_Position[Node_Bond_list[i][0]][0]-Node_Position[Node_Bond_list[i][1]][0])*(Node_Position[Node_Bond_list[i][0]][0]-Node_Position[Node_Bond_list[i][1]][0]) + (Node_Position[Node_Bond_list[i][0]][1]-Node_Position[Node_Bond_list[i][1]][1])*(Node_Position[Node_Bond_list[i][0]][1]-Node_Position[Node_Bond_list[i][1]][1]) + (Node_Position[Node_Bond_list[i][0]][2]-Node_Position[Node_Bond_list[i][1]][2])*(Node_Position[Node_Bond_list[i][0]][2]-Node_Position[Node_Bond_list[i][1]][2]));
        }
        cout<<"Using mesh initial distances as the springs nominal length."<<endl;
    } else if (Node_Bond_distances_stat=="Av"){
        cout<<"Using the average mesh bond distances ("<<Average_node_pair_length<<") as the springs nominal length."<<endl;
        for (int i=0; i<Num_of_Node_Pairs; i++) {
            Node_Bond_distances[i] = Average_node_pair_length;
        }
    } else {
        cout<<"Using "<<Node_Bond_Nominal_Length<<" as the springs nominal length."<<endl;
        for (int i=0; i<Num_of_Node_Pairs; i++) {
            Node_Bond_distances[i] = Node_Bond_Nominal_Length;
        }
    }
    
    
    
    
    
    
}
