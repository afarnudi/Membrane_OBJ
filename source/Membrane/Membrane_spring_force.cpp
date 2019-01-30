//
//  Membrane_spring_force.cpp
//  Mem
//
//  Created by Ali Farnudi on 19/08/2018.
//  Copyright © 2018 Ali Farnudi. All rights reserved.
//

#include "Membrane.h"


void Membrane::potential_1 (void){
    //modifications on this function:
    // 1- changing Membrane_Node_pair_list to Node_Bond_list
    // 2- changing Membrane_Num_of_Node_Pairs to Membrane_num_of_Triangle_Pairs (because these 2 numbers are equal)

	//cout<<"Standard Spring"<<endl;
    double le0,le1,lmax,lmin;
    double deltax,deltay,deltaz,temp_Node_distance,temp_force;
//    int pos1,pos2,pos3,pos4;  // to making calculation of surface force easier
    double temp_potential_energy = 0.0;
//    double temp_p1[3], temp_p2[3], temp_p3[3], temp_p4[3];
//    double  N1[3], N2[3], N3[3], p3p1[3], p3p2[3], p4p2[3], p4p1[3], Ep2p1[3], sinus, F0, F1[3], F2[3], F3[3], F4[3];// for exmple p3p1 is p3-p1 and ....
    
    /// calculate network force:
    int temp_Node_A, temp_Node_B;
   // le0= 0.994;
    //lmax=1.170;
    //le1=0.654;
   //lmin=0.478;
    
   le0=Max_node_pair_length - 0.09;
   lmax=Max_node_pair_length + 0.09;
   le1=Min_node_pair_length + 0.09;
   lmin=Min_node_pair_length - 0.09;
    
    Total_Potential_Energy=0.0;
    num_of_cut_off=0;
    
    for (int k=0 ; k< Num_of_Node_Pairs ; k++)
    {
        temp_Node_B=Node_Bond_list[k][0];
        temp_Node_A=Node_Bond_list[k][1];
        
        deltax=Node_Position[temp_Node_A][0]-Node_Position[temp_Node_B][0];
        deltay=Node_Position[temp_Node_A][1]-Node_Position[temp_Node_B][1];
        deltaz=Node_Position[temp_Node_A][2]-Node_Position[temp_Node_B][2];
        
        
        temp_Node_distance=sqrt(deltax*deltax+deltay*deltay+deltaz*deltaz);
        temp_force=0.0;
        double temp_exp_le0=exp(1.0/(le0-temp_Node_distance));
        double temp_exp_le1=exp(1.0/(temp_Node_distance-le1));
        //*******************************************************************************************************
        /*BUG
         |---\   |    |  /---\
         |    |  |    |  |
         |---<   |    |  |  -\
         |    |  |    |  |   |
         |---/   \----/  \---/
         */
        //*******************************************************************************************************
        //***************** Potential BUG: F=-dU/dr but in many cases I cannot determin wheather ****************
        //***************** the '-' has been implemented or not. Since the potential energy is   ****************
        //***************** never used in the code it does not a threat. ****************************************
        //*******************************************************************************************************
        
        if(temp_Node_distance >le1  & temp_Node_distance < le0 )  //free zone
        {
//            cout<<"1\n";
            temp_potential_energy=0 ; // free zone
        }
        
        if(temp_Node_distance > le0  & temp_Node_distance <lmax )  //bondforce
        {
//            cout<<"2\n";
            temp_force = -(Spring_coefficient*temp_exp_le0/(lmax-temp_Node_distance))*( 1.0/(lmax-temp_Node_distance) +  1.0/((le0-temp_Node_distance)*(le0-temp_Node_distance)));
            temp_potential_energy= Spring_coefficient*temp_exp_le0/(lmax-temp_Node_distance);
            
        }
        
        if(temp_Node_distance < le1   &  temp_Node_distance > lmin  )  // repulsive force
        {
//            cout<<"3\n";
            temp_force= (Spring_coefficient*temp_exp_le1/(temp_Node_distance-lmin))*( 1.0/(temp_Node_distance-lmin) + 1.0/((temp_Node_distance-le1)*(temp_Node_distance-le1)));                 // force on i th from j
            temp_potential_energy= Spring_coefficient*temp_exp_le1/(temp_Node_distance-lmin);
        }
        /// my cutoff for force amplitute and for avoiding leting particle scape from force trap
        if(temp_force>965.31  || temp_Node_distance>lmax )
        {
//          cout<<"4\n";
//          cout<<"temp_Node_distance"<<temp_Node_distance<<endl;
//          cout<<"temp_force_before_cut_off"<<temp_force<<endl;
            num_of_cut_off++;
            temp_force = -965.31-Spring_force_cutt_off* ( temp_Node_distance - 1.3280*Node_radius );
            temp_potential_energy=   1.81599  + 965.31 * ( temp_Node_distance - 1.3280*Node_radius )+0.5*Spring_force_cutt_off * ( temp_Node_distance - 1.3280*Node_radius ) * ( temp_Node_distance - 1.3280*Node_radius );
//            cout<<"temp_force_after_cut_off"<<temp_force<<endl;
		}
        
        
        if(temp_force<-1000.05   ||  temp_Node_distance<lmin )
        {
//            cout<<"5\n";
//            cout<<"temp_Node_distance"<<temp_Node_distance<<endl;
//            cout<<"temp_force_before_cut_off"<<temp_force<<endl;
            num_of_cut_off++;
            temp_force = 1000.05+Spring_force_cutt_off* ( 0.671965*Node_radius - temp_Node_distance );
            temp_potential_energy = 1.85038 + 1005.05 * ( 0.671965*Node_radius - temp_Node_distance )+0.5*Spring_force_cutt_off*( 0.671965*Node_radius - temp_Node_distance )*( 0.671965*Node_radius - temp_Node_distance );
//            cout<<"temp_force_after_cut_off"<<temp_force<<endl;
		}
        
        Total_Potential_Energy += temp_potential_energy;
        
        // implimentation of forces:
        Node_Force[temp_Node_A][0] += temp_force*deltax/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]);
        Node_Force[temp_Node_A][1] += temp_force*deltay/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
        Node_Force[temp_Node_A][2] += temp_force*deltaz/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
        
        Node_Force[temp_Node_B][0] += -temp_force*deltax/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]); //from j  to i
        Node_Force[temp_Node_B][1] += -temp_force*deltay/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
        Node_Force[temp_Node_B][2] += -temp_force*deltaz/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
    }
    // End of Membrane Node Pair forces
    
}
void Membrane::potential_2 (void){
	
	//cout<<"Houkian Spring"<<endl;
    
    double deltax,deltay,deltaz,temp_Node_distance,temp_force;
    
    int temp_Node_A, temp_Node_B;
    
    for (int k=0 ; k< Num_of_Node_Pairs ; k++)
    {
        temp_Node_B=Node_Bond_list[k][0];
        temp_Node_A=Node_Bond_list[k][1];
        
        deltax=Node_Position[temp_Node_A][0]-Node_Position[temp_Node_B][0];
        deltay=Node_Position[temp_Node_A][1]-Node_Position[temp_Node_B][1];
        deltaz=Node_Position[temp_Node_A][2]-Node_Position[temp_Node_B][2];
        
        
        temp_Node_distance=sqrt(deltax*deltax+deltay*deltay+deltaz*deltaz);
//        if (temp_Node_distance<Min_node_pair_length-1 || temp_Node_distance>Max_node_pair_length+1) {
//            Node_Velocity[temp_Node_A][0]/=2.0;
//            Node_Velocity[temp_Node_A][1]/=2.0;
//            Node_Velocity[temp_Node_A][2]/=2.0;
//
//            Node_Velocity[temp_Node_B][0]/=2.0;
//            Node_Velocity[temp_Node_B][1]/=2.0;
//            Node_Velocity[temp_Node_B][2]/=2.0;
//
//        }
        temp_force=-Spring_coefficient*(temp_Node_distance-Average_node_pair_length);
        
        
        // implimentation of forces:
        Node_Force[temp_Node_A][0] += temp_force*deltax/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]);
        Node_Force[temp_Node_A][1] += temp_force*deltay/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
        Node_Force[temp_Node_A][2] += temp_force*deltaz/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
        
        Node_Force[temp_Node_B][0] += -temp_force*deltax/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]); //from j  to i
        Node_Force[temp_Node_B][1] += -temp_force*deltay/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
        Node_Force[temp_Node_B][2] += -temp_force*deltaz/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
    }
    // End of Membrane Node Pair forces
}

void Membrane::FENE(void){
    
    double equi_point, delta_r_max, epsilon;
    double deltax,deltay,deltaz,temp_Node_distance,temp_force;
    //    int pos1,pos2,pos3,pos4;  // to making calculation of surface force easier
    double temp_potential_energy = 0.0;
    //    double temp_p1[3], temp_p2[3], temp_p3[3], temp_p4[3];
    //    double  N1[3], N2[3], N3[3], p3p1[3], p3p2[3], p4p2[3], p4p1[3], Ep2p1[3], sinus, F0, F1[3], F2[3], F3[3], F4[3];// for exmple p3p1 is p3-p1 and ....
    
    /// calculate network force:
    int temp_Node_A, temp_Node_B;
    // le0= 0.994;
    //lmax=1.170;
    //le1=0.654;
    //lmin=0.478;
    
    equi_point=(Max_node_pair_length + Min_node_pair_length)/2;
    delta_r_max=Max_node_pair_length - equi_point;
    delta_r_max+=delta_r_max*0.2;
    epsilon=Spring_coefficient;
    //Total_Potential_Energy=0.0;
    
    for (int k=0 ; k< Num_of_Node_Pairs ; k++)
    {
        temp_Node_B=Node_Bond_list[k][0];
        temp_Node_A=Node_Bond_list[k][1];
        
        deltax=Node_Position[temp_Node_A][0]-Node_Position[temp_Node_B][0];
        deltay=Node_Position[temp_Node_A][1]-Node_Position[temp_Node_B][1];
        deltaz=Node_Position[temp_Node_A][2]-Node_Position[temp_Node_B][2];
        
        
        temp_Node_distance=sqrt(deltax*deltax+deltay*deltay+deltaz*deltaz);
        temp_force=0.0;
        
        if (temp_Node_distance<(equi_point-delta_r_max) || temp_Node_distance>(equi_point+delta_r_max)){
//            Node_Velocity[temp_Node_A][0]*=-1;
//            Node_Velocity[temp_Node_A][1]*=-1;
//            Node_Velocity[temp_Node_A][2]*=-1;
//            Node_Velocity[temp_Node_B][0]*=-1;
//            Node_Velocity[temp_Node_B][1]*=-1;
//            Node_Velocity[temp_Node_B][2]*=-1;
            cout<<"Node distance out of bounds of the FENE cut off.\nNode numbers "<<temp_Node_A<<" and "<<temp_Node_B<<endl;
            cout<<"Node distance "<<temp_Node_distance<<endl;
            exit(EXIT_FAILURE);
            
        } else {
            double temp_R=(temp_Node_distance-equi_point)/delta_r_max;
            temp_potential_energy=-(0.5)*epsilon*delta_r_max*delta_r_max*log(1-temp_R*temp_R);
            temp_force=-epsilon*(temp_Node_distance-equi_point)/(1-temp_R*temp_R);
            
            
            Total_Potential_Energy += temp_potential_energy;
            
            // implimentation of forces:
            Node_Force[temp_Node_A][0] += temp_force*deltax/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]);
            Node_Force[temp_Node_A][1] += temp_force*deltay/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
            Node_Force[temp_Node_A][2] += temp_force*deltaz/temp_Node_distance-Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
            
            Node_Force[temp_Node_B][0] += -temp_force*deltax/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][0]-Node_Velocity[temp_Node_B][0]); //from j  to i
            Node_Force[temp_Node_B][1] += -temp_force*deltay/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][1]-Node_Velocity[temp_Node_B][1]);
            Node_Force[temp_Node_B][2] += -temp_force*deltaz/temp_Node_distance+Damping_coefficient*(Node_Velocity[temp_Node_A][2]-Node_Velocity[temp_Node_B][2]);
        }
    }
    // End of Membrane Node Pair forces
}
