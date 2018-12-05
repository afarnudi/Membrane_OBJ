//
//  interaction_neighbour_list_updaters.cpp
//  Mem
//
//  Created by Ali Farnudi on 22/08/2018.
//  Copyright © 2018 Ali Farnudi. All rights reserved.
//

#include "interaction.hpp"

void triangle_update_neighbour_list(Membrane membrane, ECM ecm, vector<int> &ECM_membrane_neighbour_list, bool &costume_interaction_flag){
    
    ECM_membrane_neighbour_list.resize(ecm.return_num_of_triangles(),-1);
    for (int triangle_index=0; triangle_index<ecm.return_num_of_triangles(); triangle_index++) {
        
        if (triangle_index%100==0) {
            cout<<"triangle_index="<<triangle_index<<endl;
        }
        
        vector<int> temp_neighbour_list_index;
        vector<double> temp_neighbour_list_distance;
        
        double normal_prob_value=0;
        for (int membrane_index=0; membrane_index<membrane.return_num_of_nodes(); membrane_index++) {
            double tri_com[3];
            double triangle_membrane_distance=return_triangle_membrane_distance(membrane, membrane_index, ecm, triangle_index, tri_com);
            
            if (triangle_membrane_distance<ecm.return_interaction_range()) {
                
                double ABxAC[3];
                ecm.triangle_normal_calculator(triangle_index, ABxAC);
                
                double relevant_position[3];
                relevant_position[0]=membrane.Node_Position[membrane_index][0]-tri_com[0];
                relevant_position[1]=membrane.Node_Position[membrane_index][1]-tri_com[1];
                relevant_position[2]=membrane.Node_Position[membrane_index][2]-tri_com[2];
                
                
                if (innerproduct(relevant_position, ABxAC)>0) {
                    temp_neighbour_list_index.push_back(membrane_index);
                    temp_neighbour_list_distance.push_back(triangle_membrane_distance);
                    normal_prob_value+=triangle_membrane_distance;
                }
                
            }
        }
        double random_num=((double) rand() / (RAND_MAX));
        double prob=0;
        for (int i=0; i<temp_neighbour_list_index.size(); i++) {
            prob+=temp_neighbour_list_distance[i]/normal_prob_value;
            if (random_num<prob) {
                ECM_membrane_neighbour_list[triangle_index]=temp_neighbour_list_index[i];
                costume_interaction_flag=true;
                //                cout<<"got one\n";
                break;
            }
        }
        
    }
    
    
}

void triangle_update_neighbour_list_2(Membrane membrane, ECM ecm, vector<int> &ECM_membrane_neighbour_list){
    
    vector<int> neighbour_pool;
    for (int i=0; i<ECM_membrane_neighbour_list.size(); i++) {
        if (ECM_membrane_neighbour_list[i]!=-1) {
            neighbour_pool.push_back(ECM_membrane_neighbour_list[i]);
        }
    }
    neighbour_pool_constructor(neighbour_pool, membrane);
    
    double range=ecm.return_interaction_range();
    
    for (int tri_index=0; tri_index<ecm.return_num_of_triangles(); tri_index++) {
        
        if (tri_index%100==0) {
            cout<<"tri_index="<<tri_index<<endl;
        }
        
        vector<int> temp_neighbour_list_index;
        vector<double> temp_neighbour_list_distance;
        
        double normal_prob_value=0;
        double tri_com[3];
        
        for (int membrane_index=0; membrane_index<neighbour_pool.size(); membrane_index++) {
            double tri_membrane_distance=return_triangle_membrane_distance(membrane, neighbour_pool[membrane_index], ecm, tri_index, tri_com);
            
            if (tri_membrane_distance<range) {
                double ABxAC[3];
                ecm.triangle_normal_calculator(tri_index, ABxAC);
                
                double relevant_position[3];
                relevant_position[0]=membrane.Node_Position[membrane_index][0]-tri_com[0];
                relevant_position[1]=membrane.Node_Position[membrane_index][1]-tri_com[1];
                relevant_position[2]=membrane.Node_Position[membrane_index][2]-tri_com[2];
                
                if (innerproduct(relevant_position, ABxAC)>0) {
                    temp_neighbour_list_index.push_back(membrane_index);
                    temp_neighbour_list_distance.push_back(tri_membrane_distance);
                    normal_prob_value+=tri_membrane_distance;
                }
                
                
            }
        }
        double random_num=((double) rand() / (RAND_MAX));
        double prob=0;
        for (int i=0; i<temp_neighbour_list_index.size(); i++) {
            prob+=temp_neighbour_list_distance[i]/normal_prob_value;
            if (random_num<prob) {
                ECM_membrane_neighbour_list[tri_index]=temp_neighbour_list_index[i];
                
                //                cout<<"got one\n";
                break;
            }
        }
        
    }
    
    
}

void triangle_update_neighbour_list_new(Membrane membrane, ECM ecm, vector<int> &ECM_membrane_neighbour_list, bool &costume_interaction_flag){
    
    ECM_membrane_neighbour_list.resize(ecm.return_num_of_triangles(),-1);
    for (int triangle_index=0; triangle_index<ecm.return_num_of_triangles(); triangle_index++) {
        
        if (triangle_index%100==0) {
            cout<<"triangle_index="<<triangle_index<<endl;
        }
        
        vector<int> temp_neighbour_list_index;
        vector<double> temp_neighbour_list_distance;
        
        double normal_prob_value=0;
        for (int membrane_index=0; membrane_index<membrane.return_num_of_nodes(); membrane_index++) {
            bool mem_node=false;
            for (int i=0; i<temp_neighbour_list_index.size(); i++) {
                if (temp_neighbour_list_index[i]==membrane_index) {
                    mem_node=true;
                }
            }
            if (!mem_node) {
                double tri_com[3];
                double triangle_membrane_distance=return_triangle_membrane_distance(membrane, membrane_index, ecm, triangle_index, tri_com);
                
                if (triangle_membrane_distance<ecm.return_interaction_range()) {
                    
                    double ABxAC[3];
                    ecm.triangle_normal_calculator(triangle_index, ABxAC);
                    
                    double relevant_position[3];
                    relevant_position[0]=membrane.Node_Position[membrane_index][0]-tri_com[0];
                    relevant_position[1]=membrane.Node_Position[membrane_index][1]-tri_com[1];
                    relevant_position[2]=membrane.Node_Position[membrane_index][2]-tri_com[2];
                    
                    
                    if (innerproduct(relevant_position, ABxAC)>0) {
                        temp_neighbour_list_index.push_back(membrane_index);
                        temp_neighbour_list_distance.push_back(triangle_membrane_distance);
                        normal_prob_value+=triangle_membrane_distance;
                    }
                    
                }
            }
        }
        double random_num=((double) rand() / (RAND_MAX));
        double prob=0;
        for (int i=0; i<temp_neighbour_list_index.size(); i++) {
            prob+=temp_neighbour_list_distance[i]/normal_prob_value;
            if (random_num<prob) {
                ECM_membrane_neighbour_list[triangle_index]=temp_neighbour_list_index[i];
                costume_interaction_flag=true;
                //                cout<<"got one\n";
                break;
            }
        }
        
    }
    
    
}

void triangle_update_neighbour_list_new_2(Membrane membrane, ECM ecm, vector<int> &ECM_membrane_neighbour_list){
    
    vector<int> neighbour_pool;
    for (int i=0; i<ECM_membrane_neighbour_list.size(); i++) {
        if (ECM_membrane_neighbour_list[i]!=-1) {
            neighbour_pool.push_back(ECM_membrane_neighbour_list[i]);
        }
    }
    neighbour_pool_constructor(neighbour_pool, membrane);
    
    double range=ecm.return_interaction_range();
    
    for (int tri_index=0; tri_index<ecm.return_num_of_triangles(); tri_index++) {
        
        if (tri_index%100==0) {
            cout<<"tri_index="<<tri_index<<endl;
        }
        
        vector<int> temp_neighbour_list_index;
        vector<double> temp_neighbour_list_distance;
        
        double normal_prob_value=0;
        double tri_com[3];
        
        for (int membrane_index=0; membrane_index<neighbour_pool.size(); membrane_index++) {
            
            bool mem_node=false;
            for (int i=0; i<temp_neighbour_list_index.size(); i++) {
                if (temp_neighbour_list_index[i]==membrane_index) {
                    mem_node=true;
                }
            }
            if (!mem_node) {
                double tri_membrane_distance=return_triangle_membrane_distance(membrane, neighbour_pool[membrane_index], ecm, tri_index, tri_com);
                
                
                if (tri_membrane_distance<range) {
                    double ABxAC[3];
                    ecm.triangle_normal_calculator(tri_index, ABxAC);
                    
                    double relevant_position[3];
                    relevant_position[0]=membrane.Node_Position[membrane_index][0]-tri_com[0];
                    relevant_position[1]=membrane.Node_Position[membrane_index][1]-tri_com[1];
                    relevant_position[2]=membrane.Node_Position[membrane_index][2]-tri_com[2];
                    
                    if (innerproduct(relevant_position, ABxAC)>0) {
                        temp_neighbour_list_index.push_back(membrane_index);
                        temp_neighbour_list_distance.push_back(tri_membrane_distance);
                        normal_prob_value+=tri_membrane_distance;
                    }
                    
                    
                }
            }
            
        }
        double random_num=((double) rand() / (RAND_MAX));
        double prob=0;
        for (int i=0; i<temp_neighbour_list_index.size(); i++) {
            prob+=temp_neighbour_list_distance[i]/normal_prob_value;
            if (random_num<prob) {
                ECM_membrane_neighbour_list[tri_index]=temp_neighbour_list_index[i];
                
                //                cout<<"got one\n";
                break;
            }
        }
        
    }
    
    
}

bool barrier_2(Membrane mem, int mem_index){
    double x=mem.Node_Position[mem_index][0];
    double z=mem.Node_Position[mem_index][2];
    double zy;
    double xyz;
    double dr=0.6;
    if (z<6 && z>-6) {
        if (x<=10 && x>= -10){
            zy=sqrt( (mem.Node_Position[mem_index][1]-4)*(mem.Node_Position[mem_index][1]-4)+(mem.Node_Position[mem_index][2])*(mem.Node_Position[mem_index][2]) );
            if (zy<(4+dr)) {
                double relevant_speed[3];
                double position[3];
                relevant_speed[0]=mem.Node_Velocity[mem_index][0];
                relevant_speed[1]=mem.Node_Velocity[mem_index][1];
                relevant_speed[2]=mem.Node_Velocity[mem_index][2];
                
                position[0]=mem.Node_Position[mem_index][0];
                position[1]=mem.Node_Position[mem_index][1]-4;
                position[2]=mem.Node_Position[mem_index][2];
                if (innerproduct(relevant_speed, position)<0) {
                    return true;
                }
            }
        } else if (x>10 && x< (14 + dr)) {
            xyz=sqrt( (mem.Node_Position[mem_index][0]-10)*(mem.Node_Position[mem_index][0]-10)+(mem.Node_Position[mem_index][1]-4)*(mem.Node_Position[mem_index][1]-4)+mem.Node_Position[mem_index][2]*mem.Node_Position[mem_index][2] );
            if (xyz<(4+dr)) {
                double relevant_speed[3];
                double position[3];
                relevant_speed[0]=mem.Node_Velocity[mem_index][0];
                relevant_speed[1]=mem.Node_Velocity[mem_index][1];
                relevant_speed[2]=mem.Node_Velocity[mem_index][2];
                
                position[0]=mem.Node_Position[mem_index][0]-10;
                position[1]=mem.Node_Position[mem_index][1]-4;
                position[2]=mem.Node_Position[mem_index][2];
                if (innerproduct(relevant_speed, position)<0) {
                    return true;
                }
            }
        } else if (x < -10 && x > -(14 + dr) ) {
            xyz=sqrt( (mem.Node_Position[mem_index][0]+10)*(mem.Node_Position[mem_index][0]+10)+(mem.Node_Position[mem_index][1]-4)*(mem.Node_Position[mem_index][1]-4)+mem.Node_Position[mem_index][2]*mem.Node_Position[mem_index][2] );
            if (xyz<(4 + dr) ) {
                double relevant_speed[3];
                double position[3];
                relevant_speed[0]=mem.Node_Velocity[mem_index][0];
                relevant_speed[1]=mem.Node_Velocity[mem_index][1];
                relevant_speed[2]=mem.Node_Velocity[mem_index][2];
                
                position[0]=mem.Node_Position[mem_index][0]+10;
                position[1]=mem.Node_Position[mem_index][1]-4;
                position[2]=mem.Node_Position[mem_index][2];
                if (innerproduct(relevant_speed, position)<0) {
                    return true;
                }
            }
        }
    }
    
    
    return false;
}
